# pixpy
Capture optris images and save to netcdf

Most initial bindings taken from https://github.com/siyka-au/pyoptris, but had some trouble getting that to work as standalone package. 


see install.sh for how it's done

edit config files schedule_config.xml sync_config.json

turn off automatic image capture: systemctl stop pixpy_app

start interactive image capture: cd /home/pi/ircam; /irimager_show config_12080019.xml (replace config file name as appropriate)

start automatic image capture: systemctl start pixpy_app

check automatic image capture: systemctl status pixpy_app

