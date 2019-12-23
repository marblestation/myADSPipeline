from adsputils import setup_logging, get_date, load_config
from myadsp import tasks, utils
from myadsp.models import KeyValue
import pyingest.parsers.arxiv as arxiv

import os
import time
import argparse
import logging
import requests
import warnings
import datetime
import gzip
import random
from requests.packages.urllib3 import exceptions
warnings.simplefilter('ignore', exceptions.InsecurePlatformWarning)

app = tasks.app
logger = setup_logging('run.py')
config = {}
config.update(load_config())


def _arxiv_ingest_complete(date=None, sleep_delay=60, sleep_timeout=7200):
    """
    Check if new arXiv records are in Solr - run before running myADS processing
    :param date: date to check arXiv records for; default is set by days-delta from today in config (times in local time)
    :param sleep_delay: number of seconds to sleep between retries
    :param sleep_timeout: number of seconds to retry in total before timing out completely
    :return: True or False
    """

    if not date:
        date = (datetime.datetime.today() - datetime.timedelta(days=config.get('ARXIV_TIMEDELTA_DAYS'))).strftime('%Y-%m-%d')
    else:
        date = get_date(date).strftime('%Y-%m-%d')

    arxiv_file = config.get('ARXIV_UPDATE_AGENT_DIR') + '/UpdateAgent.out.' + date + '.gz'

    arxiv_records = []
    with gzip.open(arxiv_file, 'r') as flist:
        for l in flist.readlines():
            # sample line: oai/arXiv.org/0706/2491 2018-06-13T01:00:29
            arxiv_records.append(l.split()[0])

    arxiv_records.sort()

    # get the highest numbered ID
    is_new = False
    while is_new is False:
        last_record = arxiv_records.pop()
        try:
            test_new = float(last_record.split('/')[-2])
            is_new = True
        except ValueError:
            continue

    # get the most recent record, convert to a filename
    last_file = config.get('ARXIV_INCOMING_ABS_DIR') + '/' + last_record

    arxiv_parser = arxiv.ArxivParser()
    with open(last_file, 'rU') as fp:
        try:
            arxiv_record = arxiv_parser.parse(fp)
        except Exception:
            # could also try to parse another record instead of failing
            logger.exception('Bad arXiv record: {0}'.format(last_file))
            return False

    try:
        last_bibc = arxiv_record.get('bibcode')
    except Exception:
        # could also try to parse another record instead of failing
        logger.exception('No bibcode found in arXiv record: {0}'.format(arxiv_record))
        return False

    total_delay = 0
    while total_delay < sleep_timeout:
        total_delay += sleep_delay
        r = requests.get('{0}?q=identifier:{1}'.format(config.get('API_SOLR_QUERY_ENDPOINT'), last_bibc),
                         headers={'Authorization': 'Bearer ' + config.get('API_TOKEN')})
        if r.status_code != 200:
            time.sleep(sleep_delay)
            logger.error('Error retrieving bibcode {0} from Solr ({1} {2}), retrying'.
                         format(last_bibc, r.status_code, r.text))
            continue

        numfound = r.json()['response']['numFound']
        if numfound == 0:
            # nothing found, try again after a sleep
            time.sleep(sleep_delay)
            logger.info('arXiv ingest not complete (test arXiv bibcode: {0}). Sleeping {1}s, for a total delay of {2}s.'
                        .format(last_bibc, sleep_delay, total_delay))
            continue
        if numfound > 1:
            # returning this as true for now, since technically something was found
            logger.error('Too many records returned for bibcode {0}'.format(last_bibc))

        return True

    logger.warning('arXiv ingest did not complete within the {0}s timeout limit. Exiting.'.format(sleep_timeout))

    return False


def _astro_ingest_complete(date=None, sleep_delay=60, sleep_timeout=7200):
    """
    Check if new astronomy records are in Solr; run before weekly processing
    :param date: check to check against astronomy bibcode list last updated date
    :param sleep_delay: number of seconds to sleep between retries
    :param sleep_timeout: number of seconds to retry in total before timing out completely
    :return: True or False
    """

    if not date:
        date = (datetime.datetime.today() - datetime.timedelta(days=config.get('ASTRO_TIMEDELTA_DAYS')))
    else:
        date = get_date(date)

    astro_file = config.get('ASTRO_INCOMING_DIR') + 'matches.input'

    # check modified datestamp on file - should be recent (otherwise contains old data)
    mod_date = datetime.datetime.fromtimestamp(os.path.getmtime(astro_file))

    # if the file is old, sleep until the file is updated
    if mod_date < date:
        total_delay = 0
        while total_delay < sleep_timeout:
            total_delay += sleep_delay
            time.sleep(sleep_delay)
            mod_date = datetime.datetime.fromtimestamp(os.path.getmtime(astro_file))
            if mod_date > date:
                break
        else:
            # timeout reached before astronomy update completed
            logger.warning('Astronomy update did not complete with the {0}s timeout limit. Exiting.'.format(sleep_timeout))

            return False

    # check that the astronomy records have made it into solr
    astro_records = []
    with open(astro_file, 'r') as flist:
        for l in flist.readlines():
            # sample line: 2019A&A...632A..94J     K58-37447
            astro_records.append(l.split()[0])

    # get several randomly selected bibcodes, in case one had ingest issues
    sample = random.sample(astro_records, config.get('ASTRO_SAMPLE_SIZE'))

    total_delay = 0
    while total_delay < sleep_timeout:
        num_sampled = 0
        for s in sample:
            num_sampled += 1
            r = requests.get('{0}?q=identifier:{1}'.format(config.get('API_SOLR_QUERY_ENDPOINT'), s),
                             headers={'Authorization': 'Bearer ' + config.get('API_TOKEN')})
            # if there's a solr error, sleep then move to the next bibcode
            if r.status_code != 200:
                time.sleep(sleep_delay)
                total_delay += sleep_delay
                logger.error('Error retrieving bibcode {0} from Solr ({1} {2}), sleeping {3}s, for a total delay of {4}s'.
                             format(s, r.status_code, r.text, sleep_delay, total_delay))
                continue

            numfound = r.json()['response']['numFound']
            if numfound == 0:
                # nothing found - if all bibcodes in the sample were tried, sleep then start the while loop again
                if num_sampled == config.get('ASTRO_SAMPLE_SIZE'):
                    time.sleep(sleep_delay)
                    total_delay += sleep_delay
                    logger.warning('Astronomy ingest not complete for all in sample (sample: {0}). Sleeping {1}s, for a total delay of {2}s.'
                                   .format(sample, sleep_delay, total_delay))
                # if we haven't tried the others in the same, try the rest
                else:
                    logger.info(
                        'Astronomy ingest not complete (test astro bibcode: {0}). Trying the next in the sample.'
                        .format(s))
                    continue
            elif numfound > 1:
                # returning this as true for now, since technically something was found
                logger.error('Too many records returned for bibcode {0}'.format(s))
                return True
            else:
                # success
                return True

    logger.warning('Astronomy ingest did not complete within the {0}s timeout limit. Exiting.'.format(sleep_timeout))

    return False


def process_myads(since=None, user_ids=None, test_send_to=None, admin_email=None, force=False,  frequency='daily', **kwargs):
    """
    Processes myADS mailings

    :param since: check for new myADS users since this date
    :param user_ids: users to process claims for, else all users - list
    :param test_send_to: for testing; process a given user ID but send the output to this email address
    :param admin_email: if provided, email is sent to this address at beginning and end of processing (does not trigger
    for processing for individual users)
    :param force: if True, will force processing of emails even if sent for a given user already that day
    :param frequency: basestring; 'daily' or 'weekly'
    :return: no return
    """
    if user_ids:
        for u in user_ids:
            tasks.task_process_myads({'userid': u, 'frequency': frequency, 'force': True, 'test_send_to': test_send_to})
            logger.info('Done (just the supplied user IDs)')
            return

    logging.captureWarnings(True)

    if admin_email:
        msg = utils.send_email(email_addr=admin_email,
                               payload_plain='Processing started for {}'.format(get_date()),
                               payload_html='Processing started for {}'.format(get_date()),
                               subject='myADS {0} processing has started'.format(frequency))

    # if since keyword not provided, since is set to timestamp of last processing
    if not since or isinstance(since, basestring) and since.strip() == "":
        with app.session_scope() as session:
            if frequency == 'daily':
                kv = session.query(KeyValue).filter_by(key='last.process.daily').first()
            else:
                kv = session.query(KeyValue).filter_by(key='last.process.weekly').first()
            if kv is not None:
                since = kv.value
            else:
                since = '1971-01-01T12:00:00Z'

    users_since_date = get_date(since)
    logger.info('Processing {0} myADS queries since: {1}'.format(frequency, users_since_date.isoformat()))

    last_process_date = get_date()
    all_users = app.get_users(users_since_date.isoformat())

    for user in all_users:
        try:
            tasks.task_process_myads.delay({'userid': user, 'frequency': frequency, 'force': force})
        except:  # potential backpressure (we are too fast)
            time.sleep(2)
            print 'Conn problem, retrying...', user
            tasks.task_process_myads.delay({'userid': user, 'frequency': frequency, 'force': force})

    # update last processed timestamp
    with app.session_scope() as session:
        if frequency == 'daily':
            kv = session.query(KeyValue).filter_by(key='last.process.daily').first()
        else:
            kv = session.query(KeyValue).filter_by(key='last.process.weekly').first()
        if kv is None:
            if frequency == 'daily':
                kv = KeyValue(key='last.process.daily', value=last_process_date.isoformat())
            else:
                kv = KeyValue(key='last.process.weekly', value=last_process_date.isoformat())
            session.add(kv)
        else:
            kv.value = last_process_date.isoformat()
        session.commit()

    print 'Done submitting {0} myADS processing tasks for {1} users.'.format(frequency, len(all_users))
    logger.info('Done submitting {0} myADS processing tasks for {1} users.'.format(frequency, len(all_users)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process user input.')

    parser.add_argument('-s',
                        '--since',
                        dest='since_date',
                        action='store',
                        default=None,
                        help='Process all new/udpated myADS users since this date, plus existing myADS users')

    parser.add_argument('-u',
                        '--uid',
                        dest='user_ids',
                        action='store',
                        default=None,
                        help='Comma delimited list of user ids to run myADS notifications for')

    parser.add_argument('-d',
                        '--daily',
                        dest='daily_update',
                        action='store_true',
                        help='Process daily arXiv myADS notifications')

    parser.add_argument('-w',
                        '--weekly',
                        dest='weekly_update',
                        action='store_true',
                        help='Process weekly myADS notifications')

    parser.add_argument('-t',
                        '--test_send_to',
                        dest='test_send_to',
                        action='store',
                        default=None,
                        help='For testing; process a given user ID but send output to this email address')

    parser.add_argument('-a',
                        '--admin_email',
                        dest='admin_email',
                        action='store',
                        default=None,
                        help='Send email to this address at beginning and end of processing')

    parser.add_argument('-f',
                        '--force',
                        dest='force',
                        action='store_true',
                        default=False,
                        help='Force processing even if already ran today')

    args = parser.parse_args()

    if args.user_ids:
        args.user_ids = [x.strip() for x in args.user_ids.split(',')]

    if args.daily_update:
        arxiv_complete = _arxiv_ingest_complete(sleep_delay=300, sleep_timeout=36000)
        if arxiv_complete:
            logger.info('arXiv ingest complete. Starting myADS processing.')
            process_myads(args.since_date, args.user_ids, args.test_send_to, args.admin_email, args.force, frequency='daily')
        else:
            logger.warning('arXiv ingest failed.')
            if args.admin_email:
                msg = utils.send_email(email_addr=args.admin_email,
                                       payload_plain='Error in the arXiv ingest',
                                       payload_html='Error in the arXiv ingest',
                                       subject='arXiv ingest failed')
    if args.weekly_update:
        astro_complete = _astro_ingest_complete(sleep_delay=300, sleep_timeout=36000)
        if astro_complete:
            logger.info('Astronomy ingest complete. Starting myADS processing.')
            process_myads(args.since_date, args.user_ids, args.test_send_to, args.admin_email, args.force, frequency='weekly')
        else:
            logger.warning('Astronomy ingest failed.')
            if args.admin_email:
                msg = utils.send_email(email_addr=args.admin_email,
                                       payload_plain='Error in the astronomy ingest',
                                       payload_html='Error in the astronomy ingest',
                                       subject='Astronomy ingest failed')
