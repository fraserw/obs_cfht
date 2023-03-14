pwd=$(pwd)
cd /arc/projects/classy/pipeline

echo Setting obs_cfht -t $(whoami)
setup obs_cfht -t $(whoami)

GREEN="\[$(tput setaf 2)\]"
RESET="\[$(tput  sgr0)\]"
export PS1="(${GREEN}lsst-cfht${RESET}) > "


cd ${pwd}
