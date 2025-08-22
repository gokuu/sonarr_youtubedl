# sonarr_youtubedl

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/fireph/sonarr_youtubedl/main.yaml?style=flat-square)
![Docker Pulls](https://img.shields.io/docker/pulls/dungfu/sonarr_youtubedl?style=flat-square)
![Docker Stars](https://img.shields.io/docker/stars/dungfu/sonarr_youtubedl?style=flat-square)
[![Docker Hub](https://img.shields.io/badge/Open%20On-DockerHub-blue)](https://hub.docker.com/r/dungfu/sonarr_youtubedl)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue)](https://github.com/fireph/sonarr_youtubedl)

sonarr_youtubedl is a [Sonarr](https://sonarr.tv/) companion script to allow the automatic downloading of web series normally not available for Sonarr to search for. Using [YT-DLP](https://github.com/yt-dlp/yt-dlp) (a youtube-dl fork with added features) it allows you to download your webseries from the list of [supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

## Features

* Downloading **Web Series** using online sources normally unavailable to Sonarr
* Ability to specify the downloaded video format globally or per series
* Downloads new episodes automatically once available
* Imports directly to Sonarr and it can then update your plex as and example
* Allows setting time offsets to handle prerelease series
* Can pass cookies.txt to handle site logins

## How do I use it

1. Find a series that is available online in the supported sites that YT-DLP can grab from.
2. Add this to Sonarr and monitor the episodes that you want.
3. Edit your config.yml accordingly so that this knows where your Sonarr is, which series you are after and where to grab it from.
4. Be aware that this requires the TVDB to match exactly what the episodes titles are in the scan, generally this is ok but as its an openly editable site sometime there can be differences.

## Supported Architectures

The architectures supported by this image are:

| Architecture | Tag |
| :----: | --- |
| x86-64 | latest |

## Version Tags

| Tag | Description |
| :----: | --- |
| latest | Current release code |

## Great how do I get started

Obviously its a docker image so you need docker, if you don't know what that is you need to look into that first.

### docker

```bash
docker create \
  --name=sonarr_youtubedl \
  -e USER_ID=1000 \
  -e GROUP_ID=1000 \
  -v /path/to/data:/config \
  -v /path/to/sonarrmedia:/sonarr_root \
  -v /path/to/logs:/logs \
  --restart unless-stopped \
  dungfu/sonarr_youtubedl
```

### docker-compose

```yaml
---
version: '3.4'
services:
  sonarr_youtubedl:
    image: dungfu/sonarr_youtubedl
    container_name: sonarr_youtubedl
    environment:
      - USER_ID=1000
      - GROUP_ID=1000
    volumes:
      - /path/to/data:/config
      - /path/to/sonarrmedia:/sonarr_root
      - /path/to/logs:/logs
```

### Docker volumes

| Parameter | Function |
| :----: | --- |
| `-v /config` | sonarr_youtubedl configs |
| `-v /sonarr_root` | Root library location from Sonarr container |
| `-v /logs` | log location |

### Environment Variables

| Parameter | Function |
| :----: | --- |
| `USER_ID` | User ID to run the container as (default: 1000) |
| `GROUP_ID` | Group ID to run the container as (default: 1000) |

**Clarification on sonarr_root**

Sonarr root is the root folder where sonarr will place the files. So in sonarr you have your files moving to `/mnt/video/tv/Helluva Boss/` as an example, in sonarr you will see that it saves this series to `/tv/Helluva Boss/` meaning the sonarr root is `/mnt/video/` as this is the root folder sonarr is working from. In the case that the path to the root folders are different in the parent filesystem (like in TrueNAS), the best way to set this up is to have your volume be: `/parent/os/path/to/video:/sonarr_root/mnt/video`.

## Configuration file

On first run the docker will create a template file in the config folder. Example [config.yml.template](./app/config.yml.template)

Copy the `config.yml.template` to a new file called `config.yml` and edit accordingly.
