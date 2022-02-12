# Vetup

Vetup is a website that pulls data from the DoD reading rooms, processes it, and makes it 
available as a website for veterans and their lawyers.

## Installation

Download this repo.  Then run the `run_docker.sh` script to call docker-compose:

```bash

./run_docker.sh
```

## Push new container image

```bash
echo $GITHUB_VETUP_PKG_TOKEN | docker login ghcr.io -u ${GITHUB_USER} --password-stdin
```



