# Download campaign finance reports
# By Christopher Schnaars, USA TODAY
# Developed with Python 2.7.4
# See README.md for complete documentation

# Import needed libraries
import ftplib
import glob
import multiprocessing
import os
import pickle
import re
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import zipfile
from scrappa import *

# Try to import user settings or set them explicitly
try:
    import usersettings

    ARCPROCDIR = usersettings.ARCPROCDIR
    ARCSVDIR = usersettings.ARCSVDIR
    RPTHOLDDIR = usersettings.RPTHOLDDIR
    RPTPROCDIR = usersettings.RPTPROCDIR
    RPTSVDIR = usersettings.RPTSVDIR
except:
    ARCPROCDIR = 'C:\\data\\FEC\\Archives\\Processed\\'
    ARCSVDIR = 'C:\\data\\FEC\\Archives\\Import\\'
    RPTHOLDDIR = 'C:\\data\\FEC\\Reports\\Hold\\'
    RPTPROCDIR = 'C:\\data\\FEC\\Reports\\Processed\\'
    RPTSVDIR = 'C:\\data\\FEC\\Reports\\Import\\'

# Other user variables
ARCFTP = 'ftp://ftp.fec.gov/FEC/electronic/'
NUMPROC = 1  # Multiprocessing processes to run simultaneously
RPTFTP = 'ftp.fec.gov'
RPTURL = 'http://docquery.fec.gov/dcdev/posted/'  # Old URL: http://query.nictusa.com/dcdev/posted/
RSSURL = 'http://efilingapps.fec.gov/rss/generate?preDefinedFilingType=ALL'  # Old URL: http://fecapps.nictusa.com/rss/generate?preDefinedFilingType=ALL


def build_archive_download_list(zipinfo={'mostrecent': '', 'badfiles':
    []}, oldarchives=[]):
    """
    Processes the zipinfo.p pickle to build a list of available archive
    files that have not been downloaded.

    oldarchives is a list of previously downloaded archives generated by
    the build_prior_archive_list function.
    """
    ftp = ftplib.FTP(RPTFTP)
    ftp.login()
    ftp.cwd('/FEC/electronic')
    files = []
    try:
        files = ftp.nlst()
    except:
        pass

    # Iterate through available files to see which ones to download
    downloads = []
    for filename in files:
        if not filename.endswith('.zip'):
            continue
        elif filename > zipinfo['mostrecent']:
            if filename not in oldarchives:
                downloads.append(filename)
        elif filename in zipinfo['badfiles']:
            if filename not in oldarchives:
                downloads.append(filename)

    return downloads


def build_prior_archive_list():
    """
    Returns a list of archives that already have been downloaded and
    saved to ARCPROCDIR or ARCSVDIR.

    NOTE: This function is slated for deprecation.  I used it for
    development and to test the implementation of the zipinfo.p pickle.
    Using the pickle saves a lot of time and disk space compared to
    warehousing all the archives.
    """
    dirs = [ARCSVDIR, ARCPROCDIR]
    archives = []

    for dir in dirs:
        for datafile in glob.glob(os.path.join(dir, '*.zip')):
            archives.append(datafile.replace(dir, ''))

    return archives


def build_prior_report_list():
    """
    Returns a list of reports housed in the directories specified by
    RPTHOLDDIR, RPTPROCDIR and RPTSVDIR.
    """
    dirs = [RPTHOLDDIR, RPTPROCDIR, RPTSVDIR]
    reports = []

    for dir in dirs:
        for datafile in glob.glob(os.path.join(dir, '*.fec')):
            reports.append(
                datafile.replace(dir, '').replace('.fec', ''))

    return reports


def consume_rss():
    """
    Returns a list of electronically filed reports included in an FEC
    RSS feed listing all reports submitted within the past seven days.
    """
    # Old URL:
    # regex = re.compile(
    #   '<link>http://query.nictusa.com/dcdev/posted/([0-9]*)\.fec</link>')
    regex = re.compile('<link>http://docquery.fec.gov/dcdev/posted/([0-9]*)\.fec</link>')
    url = urllib.request.urlopen(RSSURL)
    rss = url.read().decode()
    matches = []
    for match in re.findall(regex, rss):
        matches.append(match)

    return matches


def download_archive(archive):
    """
    Downloads a single archive file and saves it in the directory
    specified by the ARCSVDIR variable.  After downloading an archive,
    this subroutine compares the length of the downloaded file with the
    length of the source file and will try to download a file up to
    five times when the lengths don't match.
    """
    src = ARCFTP + archive
    dest = ARCSVDIR + archive
    y = 0
    # Add a header to the request
    try:
        request = urllib.request.Request(src, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36 SE 2.X MetaSr 1.0'})
        srclen = float(urllib.request.urlopen(request).info().get('Content-Length'))
    except:
        y = 5
    while y < 5:
        try:
            # I have added a header
            urllib.request.URLopener.version = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36 SE 2.X MetaSr 1.0'
            urllib.request.urlretrieve(src, dest)

            destlen = os.path.getsize(dest)

            # Repeat download up to five times if files not same size
            if srclen != destlen:
                os.remove(dest)
                y += 1
                continue
            else:
                y = 6
        except:
            y += 1
    if y == 5:
        print((src + ' could not be downloaded.'))


@crawler
def download_report(download, cr):
    """
    Downloads a single electronic report and saves it in the directory
    specified by the RPTSVDIR variable.  After downloading a report,
    this subroutine compares the length of the downloaded file with the
    length of the source file and will try to download a file up to
    five times when the lengths don't match.
    """
    # Construct file url and get length of file
    url = RPTURL + download + '.fec'
    filename = RPTSVDIR + download + '.fec'
    with cr.download_manager(url) as path:
        os.rename(path, filename)
        print(filename)


def pickle_archives(archives, oldarchives):
    """
    Rebuilds the zipinfo.p pickle and saves it in the same directory as
    this module.

    archives is a list of archive files available for download on the
    FEC website. The list is generated by the
    build_archive_download_list function.

    oldarchives is a list of previously downloaded archives generated by
    the build_prior_archive_list function.
    """
    zipinfo = {'mostrecent': '', 'badfiles': []}
    for archive in archives:
        if not archive in oldarchives:
            zipinfo['badfiles'].append(archive)
    # Sort the list
    archives.sort()
    # Set most recent to last element
    if len(archives) == 0:
        zipinfo['mostrecent'] = ''
    else:
        zipinfo['mostrecent'] = archives[-1]

    pickle.dump(zipinfo, open('zipinfo.p', 'wb'))


def unzip_archive(archive, overwrite=0):
    """
    Extracts any files housed in a specific archive that have not been
    downloaded previously.

    Set the overwrite parameter to 1 if existing files should be
    overwritten.  The default value is 0.
    """
    destdirs = [RPTSVDIR, RPTPROCDIR, RPTHOLDDIR]
    try:
        zip = zipfile.ZipFile(ARCSVDIR + archive)
        for subfile in zip.namelist():
            x = 1
            if overwrite != 1:
                for dir in destdirs:
                    if x == 1:
                        if os.path.exists(dir + subfile):
                            x = 0
            if x == 1:
                zip.extract(subfile, destdirs[0])

        zip.close()

        # If all files extracted correctly, move archive to Processed
        # directory
        os.rename(ARCSVDIR + archive, ARCPROCDIR + archive)

    except:
        print(('Files contained in ' + archive + ' could not be '
                                                'extracted. The file has been deleted so it can be '
                                                'downloaded again later.\n'))
        os.remove(ARCSVDIR + archive)


def verify_reports(rpts, downloaded):
    """
    Returns a list of indidividual reports to be downloaded.

    Specifically, this function compares a list of available reports
    that have been submitted to the FEC during the past seven days
    (rpts) with a list of previously downloaded reports (downloaded).

    For reports that already have been downloaded, the function verifies
    the length of the downloaded file matches the length of the file
    posted on the FEC website.  When the lengths do not match, the saved
    file is deleted and retained in the download list.
    """
    downloads = []
    for rpt in rpts:
        childdirs = [RPTSVDIR, RPTPROCDIR, RPTHOLDDIR]
        if rpt not in downloaded:
            downloads.append(rpt)
        else:
            # Add a header to the request.
            try:
                request = urllib.request.Request(RPTURL + rpt + '.fec', headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36 SE 2.X MetaSr 1.0'})
                srclen = float(urllib.request.urlopen(request).info().get('Content-Length'))
            except urllib.error.HTTPError:
                print((RPTURL + rpt + '.fec could not be downloaded.'))
                continue

            for child in childdirs:
                try:
                    destlen = os.path.getsize(child + rpt + '.fec')
                    if srclen != destlen:
                        downloads.append(rpt)
                        os.remove(child + rpt + '.fec')
                except:
                    pass

    return downloads


if __name__ == '__main__':
    # Attempt to fetch data specifying missing .zip files and most
    # recent .zip file downloaded
    print('Attempting to retrieve information for previously '
          'downloaded archives...')
    try:
        zipinfo = pickle.load(open("zipinfo.p", "rb"))
        print('Information retrieved successfully.\n')
    except:
        zipinfo = {'mostrecent': '', 'badfiles': []}
        print('zipinfo.p not found. Starting from scratch...\n')

    # IF YOU DON'T WANT TO DOWNLOAD ALL ARCHIVES BACK TO 2001 OR
    # OTHERWISE WANT TO MANUALLY CONTROL WHAT IS DOWNLOADED, YOU CAN
    # UNCOMMENT THE TWO LINES OF CODE BELOW AND EXPLICITLY SET THE
    # VALUES.
    # Set mostrecent to the last date you DON'T want, so if you want
    # everything since Jan. 1, 2013, set mostrecent to: '20121231.zip'
    # zipinfo['mostrecent'] = '20121231.zip' # YYYYMMDD.zip
    # zipinfo['badfiles'] = [] # You probably want to leave this blank

    # Build a list of previously downloaded archives
    print('Building a list of previously downloaded archive files...')
    oldarchives = build_prior_archive_list()
    print('Done!\n')

    # Go to FEC site and fetch a list of .zip files available
    print('Compiling a list of archives available for download...')
    archives = build_archive_download_list(zipinfo, oldarchives)
    if len(archives) == 0:
        print('No new archives found.\n')
    # If any files returned, download them using multiprocessing
    else:
        print('Done!\n')
        print(('Downloading ' + str(len(archives))
              + ' new archive(s)...'))
        pool = multiprocessing.Pool(processes=NUMPROC)
        for archive in archives:
            pool.apply_async(download_archive(archive))
        pool.close()
        pool.join()
        print('Done!\n')

        # Open each archive and extract new reports
        print('Extracting files from archives...')
        pool = multiprocessing.Pool(processes=NUMPROC)
        for archive in archives:
            # Make sure archive was downloaded
            if os.path.isfile(ARCSVDIR + archive):
                pool.apply_async(unzip_archive(archive, 0))
        pool.close()
        pool.join()
        print('Done!\n')

        # Rebuild list of downloaded archives
        print('Rebuilding list of downloaded archives...')
        oldarchives = build_prior_archive_list()
        print('Done!\n')

        # Rebuild zipinfo and save with pickle
        print('Repickling the archives. Adding salt and vinegar...')
        zipinfo = pickle_archives(archives, oldarchives)
        print('Done!\n')

    # Build list of previously downloaded reports
    print('Building a list of previously downloaded reports...')
    downloaded = build_prior_report_list()
    print('Done!\n')

    # Consume FEC's RSS feed to get list of files posted in the past
    # seven days
    print('Consuming FEC RSS feed to find new reports...')
    rpts = consume_rss()
    print(('Done! ' + str(len(rpts)) + ' reports found.\n'))

    # See whether each file flagged for download already has been
    # downloaded.  If it has, verify the downloaded file is the correct
    # length.
    print('Compiling list of reports to download...')
    newrpts = verify_reports(rpts, downloaded)
    print(('Done! ' + str(len(newrpts)) + ' reports flagged for '
                                         'download.\n'))

    # Download each of these reports
    print('Downloading new reports...')
    pool = multiprocessing.Pool(processes=NUMPROC)
    for rpt in newrpts:
        pool.apply_async(download_report(rpt))
    pool.close()
    pool.join()
    print('Done!\n')
    print('Process completed.')
