Install
=======

sudo apt-get install git nginx lynx rubygems supervisor poppler-utils vim wv htop build-essential libbz2-dev libxml2-dev libxslt-dev  libssl-dev libpython-dev libjpeg-dev zlib1g-dev letsencrypt

Compile python 2.7

/path/to/Python2.7/python bootstrap.py -c deployment.cfg
./bin/buildout -c deployment.cfg
