import argparse
import logging
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime

import requests
import schedule
import yt_dlp
from utils import (
    YoutubeDLLogger,
    checkconfig,
    convert_sonarr_to_python_format,
    offsethandler,
    sanitize_str,
    setup_logging,
    upperescape,
    ytdl_hooks,
    ytdl_hooks_debug,
)  # NOQA

# allow debug arg for verbose logging
parser = argparse.ArgumentParser(description="Process some integers.")
parser.add_argument("--debug", action="store_true", help="Enable debug logging")
args = parser.parse_args()

# setup logger
logger = setup_logging(True, True, args.debug)

date_format = "%Y-%m-%dT%H:%M:%SZ"
now = datetime.now()

CONFIGFILE = os.environ["CONFIGPATH"]
CONFIGPATH = CONFIGFILE.replace("config.yml", "")
SCANINTERVAL = 60


class SonarrYTDL(object):
    def __init__(self):
        """Set up app with config file settings"""
        cfg = checkconfig()

        # Sonarr_YTDL Setup

        try:
            self.set_scan_interval(cfg["sonarrytdl"]["scan_interval"])
            try:
                self.debug = cfg["sonarrytdl"]["debug"] in ["true", "True"]
                if self.debug:
                    logger.setLevel(logging.DEBUG)
                    for logs in logger.handlers:
                        if logs.name == "FileHandler":
                            logs.setLevel(logging.DEBUG)
                        if logs.name == "StreamHandler":
                            logs.setLevel(logging.DEBUG)
                    logger.debug("DEBUGGING ENABLED")
            except AttributeError:
                self.debug = False
        except Exception:
            sys.exit("Error with sonarrytdl config.yml values.")

        # Sonarr Setup
        try:
            api = "api"
            scheme = "http"
            basedir = ""
            if cfg["sonarr"].get("version", "").lower() == "v4":
                api = "api/v3"
                logger.debug("Sonarr api set to v4")
            if cfg["sonarr"]["ssl"].lower() == "true":
                scheme = "https"
            if cfg["sonarr"].get("basedir", ""):
                basedir = "/" + cfg["sonarr"].get("basedir", "")

            self.base_url = "{0}://{1}:{2}{3}".format(
                scheme, cfg["sonarr"]["host"], str(cfg["sonarr"]["port"]), basedir
            )
            self.sonarr_api_version = api
            self.api_key = cfg["sonarr"]["apikey"]
        except Exception:
            sys.exit("Error with sonarr config.yml values.")

        # YTDL Setup
        try:
            self.ytdl_format = cfg["ytdl"]["default_format"]
        except Exception:
            sys.exit("Error with ytdl config.yml values.")

        # Naming Configuration from Sonarr
        naming_configuration = self.get_naming_configuration()

        if naming_configuration is not None:
            self.naming_configuration = naming_configuration
        else:
            self.naming_configuration = None

        # YTDL Setup
        try:
            self.series = cfg["series"]
        except Exception:
            sys.exit("Error with series config.yml values.")

    def get_naming_configuration(self):
        """Returns the naming configuration for the given series"""
        logger.debug("Begin call Sonarr for naming configuration")
        try:
            res = self.request_get(
                "{}/{}/config/naming".format(self.base_url, self.sonarr_api_version)
            )
            return res.json()
        except Exception as e:
            logger.error("Failed to get naming configuration: {}".format(e))
            return None

    def get_episodes_by_series_id(self, series_id):
        """Returns all episodes for the given series"""
        logger.debug(
            "Begin call Sonarr for all episodes for series_id: {}".format(series_id)
        )
        args = {"seriesId": series_id}
        try:
            res = self.request_get(
                "{}/{}/episode".format(self.base_url, self.sonarr_api_version), args
            )
            return res.json()
        except Exception as e:
            logger.error(
                "Failed to get episodes for series_id {}: {}".format(series_id, e)
            )
            return []

    def get_episode_files_by_series_id(self, series_id):
        """Returns all episode files for the given series"""
        try:
            res = self.request_get(
                "{}/{}/episodefile?seriesId={}".format(
                    self.base_url, self.sonarr_api_version, series_id
                )
            )
            return res.json()
        except Exception as e:
            logger.error(
                "Failed to get episode files for series_id {}: {}".format(series_id, e)
            )
            return []

    def get_series(self):
        """Return all series in your collection"""
        logger.debug("Begin call Sonarr for all available series")
        try:
            res = self.request_get(
                "{}/{}/series".format(self.base_url, self.sonarr_api_version)
            )
            return res.json()
        except Exception as e:
            logger.error("Failed to get series from Sonarr: {}".format(e))
            return []

    def get_series_by_series_id(self, series_id):
        """Return the series with the matching ID or 404 if no matching series is found"""
        logger.debug(
            "Begin call Sonarr for specific series series_id: {}".format(series_id)
        )
        try:
            res = self.request_get(
                "{}/{}/series/{}".format(
                    self.base_url, self.sonarr_api_version, series_id
                )
            )
            return res.json()
        except Exception as e:
            logger.error(
                "Failed to get series with series_id {}: {}".format(series_id, e)
            )
            return None

    def request_get(self, url, params=None):
        """Wrapper on the requests.get"""
        logger.debug("Begin GET with url: {}".format(url))
        args = {"apikey": self.api_key}
        if params is not None:
            logger.debug("Begin GET with params: {}".format(params))
            args.update(params)
        url = "{}?{}".format(url, urllib.parse.urlencode(args))
        try:
            res = requests.get(url, timeout=30)
            res.raise_for_status()  # Raise an exception for bad status codes
            return res
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection error when calling Sonarr API: {}".format(e))
            raise
        except requests.exceptions.Timeout as e:
            logger.error("Timeout error when calling Sonarr API: {}".format(e))
            raise
        except requests.exceptions.HTTPError as e:
            logger.error("HTTP error when calling Sonarr API: {}".format(e))
            logger.error("Response status code: {}".format(res.status_code))
            logger.error("Response content: {}".format(res.text))
            raise
        except requests.exceptions.RequestException as e:
            logger.error("Request error when calling Sonarr API: {}".format(e))
            raise

    def request_put(self, url, params=None, jsondata=None):
        """Wrapper on the requests.post"""
        logger.debug("Begin POST with url: {}".format(url))
        headers = {
            "Content-Type": "application/json",
        }
        args = {"apikey": self.api_key}
        if params is not None:
            logger.debug("Begin POST with params: {}".format(params))
            args.update(params)

        try:
            res = requests.post(
                url, headers=headers, params=args, json=jsondata, timeout=30
            )
            res.raise_for_status()  # Raise an exception for bad status codes
            logger.debug(
                "POST request successful, status code: {}".format(res.status_code)
            )
            return res
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection error when calling Sonarr API: {}".format(e))
            raise
        except requests.exceptions.Timeout as e:
            logger.error("Timeout error when calling Sonarr API: {}".format(e))
            raise
        except requests.exceptions.HTTPError as e:
            logger.error("HTTP error when calling Sonarr API: {}".format(e))
            logger.error("Response status code: {}".format(res.status_code))
            logger.error("Response content: {}".format(res.text))
            raise
        except requests.exceptions.RequestException as e:
            logger.error("Request error when calling Sonarr API: {}".format(e))
            raise

    def rescanseries(self, series_id):
        """Refresh series information from trakt and rescan disk"""
        logger.debug("Begin call Sonarr to rescan for series_id: {}".format(series_id))
        data = {"name": "RescanSeries", "seriesId": int(series_id)}
        try:
            res = self.request_put(
                "{}/{}/command".format(self.base_url, self.sonarr_api_version),
                None,
                data,
            )
            return res.json()
        except Exception as e:
            logger.error(
                "Failed to rescan series with series_id {}: {}".format(series_id, e)
            )
            return None

    def filterseries(self):
        """Return all series in Sonarr that are to be downloaded by youtube-dl"""
        series = self.get_series()
        matched = []
        for ser in series[:]:
            for wnt in self.series:
                if wnt["title"] == ser["title"]:
                    # Set default values
                    ser["subtitles"] = False
                    ser["playlistreverse"] = True
                    ser["subtitles_languages"] = ["en"]
                    ser["subtitles_autogenerated"] = False
                    # Update values
                    if "regex" in wnt:
                        regex = wnt["regex"]
                        if "sonarr" in regex:
                            ser["sonarr_regex_match"] = regex["sonarr"]["match"]
                            ser["sonarr_regex_replace"] = regex["sonarr"]["replace"]
                        if "site" in regex:
                            ser["site_regex_match"] = regex["site"]["match"]
                            ser["site_regex_replace"] = regex["site"]["replace"]
                    if "offset" in wnt:
                        ser["offset"] = wnt["offset"]
                    if "cookies_file" in wnt:
                        ser["cookies_file"] = wnt["cookies_file"]
                    if "format" in wnt:
                        ser["format"] = wnt["format"]
                    if "playlistreverse" in wnt:
                        if wnt["playlistreverse"] == "False":
                            ser["playlistreverse"] = False
                    if "subtitles" in wnt:
                        ser["subtitles"] = True
                        if "languages" in wnt["subtitles"]:
                            ser["subtitles_languages"] = wnt["subtitles"]["languages"]
                        if "autogenerated" in wnt["subtitles"]:
                            ser["subtitles_autogenerated"] = wnt["subtitles"][
                                "autogenerated"
                            ]
                    ser["url"] = wnt["url"]
                    matched.append(ser)
        for check in matched:
            if not check["monitored"]:
                logger.warn("{0} is not currently monitored".format(ser["title"]))
        del series[:]
        return matched

    def getseriesepisodes(self, series):
        needed = []
        for ser in series[:]:
            episodes = self.get_episodes_by_series_id(ser["id"])
            for eps in episodes[:]:
                eps_date = now
                if "airDateUtc" in eps:
                    eps_date = datetime.strptime(eps["airDateUtc"], date_format)
                    if "offset" in ser:
                        eps_date = offsethandler(eps_date, ser["offset"])
                if not eps["monitored"]:
                    episodes.remove(eps)
                elif eps["hasFile"]:
                    episodes.remove(eps)
                elif eps_date > now:
                    episodes.remove(eps)
                else:
                    if "sonarr_regex_match" in ser:
                        match = ser["sonarr_regex_match"]
                        replace = ser["sonarr_regex_replace"]
                        eps["title"] = re.sub(match, replace, eps["title"])
                    needed.append(eps)
                    continue
            if len(episodes) == 0:
                logger.info("{0} no episodes needed".format(ser["title"]))
                series.remove(ser)
            else:
                logger.info(
                    "{0} missing {1} episodes".format(ser["title"], len(episodes))
                )
                for i, e in enumerate(episodes):
                    logger.info(
                        "  {0}: {1} - {2}".format(i + 1, ser["title"], e["title"])
                    )
        return needed

    def appendcookie(self, ytdlopts, cookies=None):
        """Checks if specified cookie file exists in config
        - ``ytdlopts``: Youtube-dl options to append cookie to
        - ``cookies``: filename of cookie file to append to Youtube-dl opts
        returns:
            ytdlopts
                original if problem with cookies file
                updated with cookies value if cookies file exists
        """
        if cookies is not None:
            cookie_path = os.path.abspath(CONFIGPATH + cookies)
            cookie_exists = os.path.exists(cookie_path)
            if cookie_exists is True:
                ytdlopts.update({"cookiefile": cookie_path})
                # if self.debug is True:
                logger.debug("  Cookies file used: {}".format(cookie_path))
            if cookie_exists is False:
                logger.warning("  cookie files specified but doesnt exist.")
            return ytdlopts
        else:
            return ytdlopts

    def customformat(self, ytdlopts, customformat=None):
        """Checks if specified cookie file exists in config
        - ``ytdlopts``: Youtube-dl options to change the ytdl format for
        - ``customformat``: format to download
        returns:
            ytdlopts
                original: if no custom format
                updated: with new format value if customformat exists
        """
        if customformat is not None:
            ytdlopts.update({"format": customformat})
            return ytdlopts
        else:
            return ytdlopts

    def ytdl_eps_search_opts(self, regextitle, playlistreverse, cookies=None):
        ytdlopts = {
            "ignoreerrors": True,
            "playlistreverse": playlistreverse,
            "matchtitle": regextitle,
            "quiet": True,
        }
        if self.debug is True:
            ytdlopts.update(
                {
                    "quiet": False,
                    "logger": YoutubeDLLogger(),
                    "progress_hooks": [ytdl_hooks],
                }
            )
        ytdlopts = self.appendcookie(ytdlopts, cookies)
        if self.debug is True:
            logger.debug("Youtube-DL opts used for episode matching")
            logger.debug(ytdlopts)
        return ytdlopts

    def ytsearch(self, ydl_opts, playlist):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(playlist, download=False)
        except Exception as e:
            logger.error(e)
        else:
            video_url = None
            if "entries" in result and len(result["entries"]) > 0:
                try:
                    video_url = result["entries"][0].get("webpage_url")
                except Exception as e:
                    logger.error(e)
            else:
                video_url = result.get("webpage_url")
            if playlist == video_url:
                return False, ""
            if video_url is None:
                logger.error("No video_url")
                return False, ""
            else:
                return True, video_url

    def get_episode_filename(self, series, episode):
        logger.debug("Getting episode filename")

        if self.naming_configuration is not None:
            template = "/sonarr_root{path}/{seasonFolderFormat}/{standardEpisodeFormat}".format(
              path = series["path"],
              seasonFolderFormat = self.naming_configuration["seasonFolderFormat"],
              standardEpisodeFormat = self.naming_configuration["standardEpisodeFormat"],
            )
            logger.debug(f"Converting Sonarr template: {template}")
            template = convert_sonarr_to_python_format(template)
            logger.debug(f"Using python template: {template}")

            # {Series Title} - s{season:00}e{episode:00} - {Episode Title}
            return template.format(
                SeriesTitle = sanitize_str(series["title"]),
                season = episode["seasonNumber"],
                episode = episode["episodeNumber"],
                EpisodeTitle = sanitize_str(episode["title"]),
            )
        else:
            return "/sonarr_root{0}/{1}/{2} - S{3:02d}E{4:02d} - {5} - WEB-DL-SonarrYTDL.%(ext)s".format(
                series["path"],
                "Specials" if episode["seasonNumber"] == 0 else f"Season {episode['seasonNumber']}",
                sanitize_str(series["title"]),
                episode["seasonNumber"],
                episode["episodeNumber"],
                sanitize_str(episode["title"]),
            )

    def download(self, series, episodes):
        if len(series) != 0:
            logger.info("Processing Wanted Downloads")
            for s, ser in enumerate(series):
                logger.info("  {}:".format(ser["title"]))
                for e, eps in enumerate(episodes):
                    if ser["id"] == eps["seriesId"]:
                        cookies = None
                        url = ser["url"]
                        if "cookies_file" in ser:
                            cookies = ser["cookies_file"]
                        ydleps = self.ytdl_eps_search_opts(
                            upperescape(eps["title"]), ser["playlistreverse"], cookies
                        )
                        found, dlurl = self.ytsearch(ydleps, url)
                        if found:
                            logger.info(
                                "    {}: Found - {}:".format(e + 1, eps["title"])
                            )

                            filename = self.get_episode_filename(ser, eps)
                            logger.debug(f"Got filename: {filename}")

                            ytdl_format_options = {
                                "format": self.ytdl_format,
                                "quiet": True,
                                "merge-output-format": "mkv",
                                "outtmpl": filename,
                                "progress_hooks": [ytdl_hooks],
                                "noplaylist": True,
                                "retry_sleep": 5,
                                "postprocessors": [
                                    {
                                        "key": "FFmpegVideoRemuxer",
                                        "preferedformat": "mkv",
                                    }
                                ],
                            }
                            ytdl_format_options = self.appendcookie(
                                ytdl_format_options, cookies
                            )
                            if "format" in ser:
                                ytdl_format_options = self.customformat(
                                    ytdl_format_options, ser["format"]
                                )
                            if "subtitles" in ser:
                                if ser["subtitles"]:
                                    ytdl_format_options.update(
                                        {
                                            "writesubtitles": True,
                                            "writeautomaticsub": ser[
                                                "subtitles_autogenerated"
                                            ],
                                            "subtitleslangs": ser[
                                                "subtitles_languages"
                                            ],
                                            "sleep_interval": 2,
                                            "sleep_interval_requests": 3,
                                            "retries": 10,
                                        }
                                    )
                                    ytdl_format_options["postprocessors"].append(
                                        {
                                            "key": "FFmpegSubtitlesConvertor",
                                            "format": "srt",
                                        }
                                    )
                                    ytdl_format_options["postprocessors"].append(
                                        {
                                            "key": "FFmpegEmbedSubtitle",
                                        }
                                    )

                            if self.debug is True:
                                ytdl_format_options.update(
                                    {
                                        "quiet": False,
                                        "logger": YoutubeDLLogger(),
                                        "progress_hooks": [ytdl_hooks_debug],
                                    }
                                )
                                logger.debug("Youtube-DL opts used for downloading")
                                logger.debug(ytdl_format_options)
                            try:
                                yt_dlp.YoutubeDL(ytdl_format_options).download([dlurl])
                                self.rescanseries(ser["id"])
                                logger.info(
                                    "      Downloaded - {}".format(eps["title"])
                                )
                            except Exception as e:
                                logger.error(
                                    "      Failed - {} - {}".format(eps["title"], e)
                                )
                        else:
                            logger.info(
                                "    {}: Missing - {}:".format(e + 1, eps["title"])
                            )
        else:
            logger.info("Nothing to process")

    def set_scan_interval(self, interval):
        global SCANINTERVAL
        if interval != SCANINTERVAL:
            SCANINTERVAL = interval
            logger.info(
                "Scan interval set to every {} minutes by config.yml".format(interval)
            )
        else:
            logger.info(
                "Default scan interval of every {} minutes in use".format(interval)
            )
        return


def main():
    client = SonarrYTDL()
    series = client.filterseries()
    episodes = client.getseriesepisodes(series)
    client.download(series, episodes)
    logger.info("Waiting...")


if __name__ == "__main__":
    logger.info("Initial run")
    main()
    schedule.every(int(SCANINTERVAL)).minutes.do(main)
    while True:
        schedule.run_pending()
        time.sleep(1)
