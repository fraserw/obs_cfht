
__all__ = ["CfhtIsrTaskConfig", "CfhtIsrTask"]

import numpy as np

import lsst.pex.config as pexConfig
from lsst.ip.isr import IsrTask


class CfhtIsrTaskConfig(IsrTask.ConfigClass):
    safe = pexConfig.Field(
        dtype=float,
        doc="Safety margin for CFHT sensors gain determination",
        default=0.95,
    )

    def setDefaults(self):
        IsrTask.ConfigClass.setDefaults(self)


class CfhtIsrTask(IsrTask):
    ConfigClass = CfhtIsrTaskConfig

    def run(self, ccdExposure, bias=None, linearizer=None, dark=None, flat=None, defects=None,
            fringes=None, bfKernel=None, **kwds):
        """Perform instrument signature removal on an exposure

        Steps include:
        - Detect saturation, apply overscan correction, bias, dark and flat
        - Perform CCD assembly
        - Interpolate over defects, saturated pixels and all NaNs
        - Persist the ISR-corrected exposure as "postISRCCD" if
          config.doWrite is True

        Parameters
        ----------
        ccdExposure : `lsst.afw.image.Exposure`
            Detector data.
        bias : `lsst.afw.image.exposure`
            Exposure of bias frame.
        linearizer : `lsst.ip.isr.LinearizeBase` callable
            Linearizing functor; a subclass of lsst.ip.isr.LinearizeBase.
        dark : `lsst.afw.image.exposure`
            Exposure of dark frame.
        flat : `lsst.afw.image.exposure`
            Exposure of flatfield.
        defects : `list`
            list of detects
        fringes : `lsst.afw.image.Exposure` or list `lsst.afw.image.Exposure`
            exposure of fringe frame or list of fringe exposure
        bfKernel : None
            kernel used for brighter-fatter correction; currently unsupported
        **kwds : `dict`
            additional kwargs forwarded to IsrTask.run.

        Returns
        -------
        struct : `lsst.pipe.base.Struct` with fields:
            - exposure: the exposure after application of ISR
        """
        if bfKernel is not None:
            raise ValueError("CFHT ISR does not currently support brighter-fatter correction.")

        ccd = ccdExposure.getDetector()
        floatExposure = self.convertIntToFloat(ccdExposure)
        metadata = floatExposure.getMetadata()

        # Detect saturation
        # Saturation values recorded in the fits hader is not reliable, try to
        # estimate it from the pixel values.
        # Find the peak location in the high end part the pixel values'
        # histogram and set the saturation level at safe * (peak location)
        # where safe is a configurable parameter (typically 0.95)
        image = floatExposure.getMaskedImage().getImage()
        imageArray = image.getArray()
        maxValue = np.max(imageArray)
        if maxValue > 60000.0:
            hist, bin_edges = np.histogram(imageArray.ravel(), bins=100, range=(60000.0, maxValue+1.0))
            saturate = int(self.config.safe*bin_edges[np.argmax(hist)])
        else:
            saturate = metadata.getScalar("SATURATE")
        self.log.info("Saturation set to %d" % saturate)

        tempCcd = ccd.rebuild()
        tempCcd.clear()
        for amp in ccd:
            tempAmp = amp.rebuild()
            tempAmp.setSaturation(saturate)
            if tempAmp.getName() == "A":
                tempAmp.setGain(metadata.getScalar("GAINA"))
                rdnA = metadata.getScalar("RDNOISEA")
                # Check if the noise value is making sense for this amp. If
                # not, replace with value stored in RDNOISE slot. This change
                # is necessary to process some old CFHT images
                # (visit : 7xxxxx) where RDNOISEA/B = 65535
                if rdnA > 60000.0:
                    rdnA = metadata.getScalar("RDNOISE")
                tempAmp.setReadNoise(rdnA)
            elif tempAmp.getName() == "B":
                tempAmp.setGain(metadata.getScalar("GAINB"))
                rdnB = metadata.getScalar("RDNOISEB")
                # Check if the noise value is making sense for this amp.
                # If not, replace with value
                # stored in RDNOISE slot. This change is necessary to process
                # some old CFHT images
                # (visit : 7xxxxx) where RDNOISEA/B = 65535
                if rdnB > 60000.0:
                    rdnB = metadata.getScalar("RDNOISE")
                tempAmp.setReadNoise(rdnB)
            else:
                raise ValueError("Unexpected amplifier name : %s"%(amp.getName()))
            tempCcd.append(tempAmp)

        ccd = tempCcd.finish()
        ccdExposure.setDetector(ccd)
        return IsrTask.run(self,
                           ccdExposure=ccdExposure,
                           bias=bias,
                           linearizer=linearizer,
                           dark=dark,
                           flat=flat,
                           defects=defects,
                           fringes=fringes,
                           **kwds
                           )
