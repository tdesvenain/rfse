#!/bin/bash
scp tdesvenain@intranet.heleneducourant.fr:~/rfse/zinstance/var/filestorage/Data.fs var/filestorage/
rsync -a tdesvenain@intranet.heleneducourant.fr:~/rfse/zinstance/var/blobstorage/ var/blobstorage/
