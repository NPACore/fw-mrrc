import redcap    # pip install PyCap # doi:10.5281/zenodo.9917
import flywheel  # flywheel-sdk
import numpy as np
import pandas as pd
import warnings
import os
import re
import subprocess as sp


def get_key(envvar=None, passname=None, keyfile=None):
    "get API key from Env, 'pass' cli program, or file"
    # try the enviornment first
    key = os.environ.get(envvar) if envvar is not None else None

    # try the pass command
    if not key and keyfile is not None:
        try:
            key = sp.check_output(f'pass {passname}', shell=True).\
                decode().strip()
        except sp.CalledProcessError:
            pass

    # and finally a file
    if not key and keyfile is not None and os.path.isfile(keyfile):
        with open(keyfile, 'r') as fhandle:
            key = fhandle.readline().strip()
            # special case flywheel json
            json = re.search('key": "([^"]*)"', key)
            if json:
                key = json.groups(0)[0]

    if not key:
        msg = f"no key! Tried {envvar}, pass {passname}, {keyfile}"
        raise Exception(msg)
    return key


def redcap_records(**kargs):
    """get redcap records. will try to find API key.
    kargs passed on to export_records
    e.g. recap_records(records=['12001'])
         default is all
    """
    rc_url = os.environ.get('REDCAP_URL',
                            'https://www.ctsiredcap.pitt.edu/redcap/api/')
    rc_key = get_key('REDCAP_KEY', 'redcap_habit', '.redcap-apikey')
    proj = redcap.Project(rc_url, rc_key)
    return proj.export_records(format_type="df", **kargs)


def ymd_trans(date_str):
    """trun YYYY-MM-DD HH:MM:SS into YYYYMMDD. pd.nan to '' """
    return re.sub(' .*|-', '', date_str) if pd.notnull(date_str) else ''


def fw_sessions(project_path='luna/wpc-8620-habit'):
    """ for every flywheel session, lookup redcap info

    TODO:
     * check what flywheel already has?
     * should iterate over sessions. get date from first acqusitions?
    """
    fw_key = get_key("FLYWHEEL_KEY", "flywheel-apikey",
                     os.path.expanduser("~/.config/flywheel/user.json"))
    fw = flywheel.Client(fw_key)
    proj = fw.resolve(project_path)
    sess_ids = [x.code for x in proj.children]
    # date = proj.children[0].sessions()[0].acquisitions()[0].timestamp.strftime("%Y%m%d")

    # nested index hard to match against
    redcap_df = redcap_records().reset_index()
    # reformat date to match flywheel sesion id
    # date w/o hyphens and sans timestamp
    redcap_df['mri_session_id'] = redcap_df.mri_sub_arrival.map(ymd_trans)
    data_for_fw = []
    for ses in sess_ids:
        (subj, sesid) = ses.split("_")
        ses_data = redcap_df[(redcap_df.redcap_id == subj) &
                             (redcap_df.mri_session_id == sesid)].reset_index()

        if ses_data.shape[0] != 1:
            warnings.warn(f"{ses} data has {ses_data.shape[0]} MR matches in redcap!")
            continue

        age = ses_data.age_at_scan[0]

        ## get value from another event
        #
        # currently only have _arm_1
        # pd.unique(redcap_df.redcap_event_name)
        # ['recruit_arm_1', 'screener_arm_1', 'behavorial_arm_1', 'mr_arm_1']

        # get screen row at this timepoint (event/arm)
        # prserver _TPNUM by just replacing MR
        beh_event = re.sub('^mr', 'behavorial',
                           ses_data.redcap_event_name[0])

        beh_data = redcap_df[(redcap_df.redcap_id == subj) &
                             (redcap_df.redcap_event_name == beh_event)].\
            reset_index()

        if beh_data.shape[0] != 1:
            warnings.warn(f"{ses} data has {beh_data.shape[0]} beh matches in redcap!")
            continue

        upps_info = beh_data.upps_reservedattitude[0]

        data_for_fw.append({'age': age, 'upps': upps_info, 'code': ses})

    print(data_for_fw)


if __name__ == "__main__":
    fw_sessions('luna/wpc-8620-habit')
