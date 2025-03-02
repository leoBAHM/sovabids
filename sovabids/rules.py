"""Module dealing with the rules for bids conversion."""
import os
import json
import yaml
import argparse

from copy import deepcopy
from mne_bids import write_raw_bids,BIDSPath
from mne_bids.utils import _handle_datatype,_write_json,_get_ch_type_mapping
from mne_bids.path import _parse_ext
from mne.io import read_raw
from pandas import read_csv
from traceback import format_exc

from sovabids.settings import NULL_VALUES,SUPPORTED_EXTENSIONS
from sovabids.files import _get_files
from sovabids.dicts import deep_merge_N
from sovabids.parsers import parse_from_regex,parse_from_placeholder
from sovabids.bids import update_dataset_description

def get_info_from_path(path,rules):
    """Parse information from a given path, given a set of rules.

    Parameters
    ----------

    path : str
        The path from where we want to extract information.
    rules : dict
        A dictionary following the "Rules File Schema".

    Notes
    --------

    See the Rules File Schema documentation for the expected schema of the dictionary.
    """
    rules__ = deepcopy(rules)
    patterns_extracted = {}
    non_bids_rules = rules__.get('non-bids',{})
    if 'path_analysis' in non_bids_rules:
        path_analysis = non_bids_rules['path_analysis']
        pattern = path_analysis.get('pattern','')
        # Check if regex
        if 'fields' in path_analysis:
            patterns_extracted = parse_from_regex(path,pattern,path_analysis.get('fields',[]))
        else: # Assume placeholder notation
            encloser = path_analysis.get('encloser','%')
            matcher = path_analysis.get('matcher','(.+)')
            patterns_extracted = parse_from_placeholder(path,pattern,encloser,matcher)
    if 'ignore' in patterns_extracted:
        del patterns_extracted['ignore']
    # this what needed because using rules__.update(patterns_extracted) replaced it all
    rules__ = deep_merge_N([rules__,patterns_extracted])
    return rules__

def get_files(source_path,rules):
    """Recursively scan the directory for valid files, returning a list with the full-paths to each.
    
    The valid files are given by the 'non-bids.eeg_extension' rule. See the "Rules File Schema".

    Parameters
    ----------

    source_path : str
        The path we want to obtain the files from.
    rules : str|dict
        The path to the rules file, or the rules dictionary.

    Returns
    -------

    filepaths : list of str
        A list containing the path to each valid file in the source_path.
    """
    rules_ = load_rules(rules)

    if isinstance(source_path,str):

        # Generate all files
        try:
            extensions = rules_['non-bids']['eeg_extension']
        except:
            extensions = deepcopy(SUPPORTED_EXTENSIONS)

        if isinstance(extensions,str):
            extensions = [extensions]

        # append dot to extensions if missing
        extensions = [x if x[0]=='.' else '.'+x for x in extensions]

        filepaths = _get_files(source_path)
        filepaths = [x for x in filepaths if os.path.splitext(x)[1] in extensions]
    else:
        raise ValueError('The source_path should be str.')
    return filepaths
def load_rules(rules):
    """Load rules if given a path, bypass if given a dict.

    Parameters
    ----------
    
    rules : str|dict
        The path to the rules file, or the rules dictionary.

    Returns
    -------

    dict
        The rules dictionary.
    """
    if not isinstance(rules,dict):
        with open(rules,encoding="utf-8") as f:
            return yaml.load(f,yaml.FullLoader)
    return deepcopy(rules)

def apply_rules_to_single_file(file,rules,bids_path,write=False,preview=False,logger=None):
    """Apply rules to a single file.

    Parameters
    ----------

    file : str
        Path to the file.
    rules : str|dict
        Path to the rules file or rules dictionary.
    bids_path : str
        Path to the bids directory
    write : bool, optional
        Whether to write output or not.
    preview : bool, optional
        Whether to return a dictionary with a "preview" of the conversion.
        This dict will have the same schema as the "Mapping File Schema" but may have flat versions of its fields.
        *UNDER CONSTRUCTION*
    logger : logging.logger object, optional
        The logger, if None logging is skipped.

    Returns
    -------

    mapping : dict
        The mapping obtained from applying the rules to the given file
    preview : bool|dict
        If preview = False, then False. If True, then the preview dictionary.
    """
    f = file
    if not isinstance(rules,dict):
        rules__ = load_rules(rules)
    else:
        rules__ = deepcopy(rules) #otherwise the deepmerge wont update the values for a new file
    # Upon reading RAW MNE makes the assumptions
    raw = read_raw(f,preload=False)#not write)

    # First get info from path

    rules__ = get_info_from_path(f,rules__)

    # Apply Rules
    assert 'entities' in rules__
    entities = rules__['entities'] # this key has the same fields as BIDSPath constructor argument

    if 'sidecar' in rules__:
        sidecar = rules__['sidecar']
        if "PowerLineFrequency" in sidecar and sidecar['PowerLineFrequency'] not in NULL_VALUES:
            raw.info['line_freq'] = sidecar["PowerLineFrequency"]  # specify power line frequency as required by BIDS
        # Should we try to infer the line frequency automatically from the psd?

    if 'channels' in rules__:
        channels = rules__['channels']
        if "name" in channels:
            raw.rename_channels(channels['name'])
        if "type" in channels: # We overwrite whatever channel types we can on the files
            # https://github.com/mne-tools/mne-bids/blob/3711613edc0e2039c921ad9b1a32beccc52156b1/mne_bids/utils.py#L78-L83
            # care should be taken with the channel counts set up by mne-bids https://github.com/mne-tools/mne-bids/blob/main/mne_bids/write.py#L774-L782
            # but right now is inofensive
            types = channels['type']
            types = {key:_get_ch_type_mapping(fro='bids',to='mne').get(val,None) for key,val in types.items() }
            valid_types = {k: v for k, v in types.items() if v is not None}
            raw.set_channel_types(valid_types)
    if 'non-bids' in rules__:
        non_bids = rules__['non-bids']
        if "code_execution" in non_bids:
            if isinstance(non_bids["code_execution"],str):
                non_bids["code_execution"] = [non_bids["code_execution"]]
            if isinstance(non_bids["code_execution"],list):
                for command in non_bids["code_execution"]:
                    try:
                        exec(command)
                    except:
                        error_string = 'There was an error with the follwing command:\n'+command+'\ngiving the following traceback:\n'+format_exc()
                        print(error_string)
                        #maybe log errors here?
                        #or should we raise an exception?


        bids_path = BIDSPath(**entities,root=bids_path)

        real_times = raw.times[-1]
        if write:
            write_raw_bids(raw, bids_path=bids_path,overwrite=True)
        else:
            if preview:
                max_samples = min(10,raw.last_samp)
                tmax = max_samples/raw.info['sfreq']
                raw.crop(tmax=tmax)
                orig_files = _get_files(bids_path.root)
                write_raw_bids(raw, bids_path=bids_path,overwrite=True,format='BrainVision',allow_preload=True,verbose=False)
            else:
            # These lines are taken from mne_bids.write
                raw_fname = raw.filenames[0]
                if '.ds' in os.path.dirname(raw.filenames[0]):
                    raw_fname = os.path.dirname(raw.filenames[0])
                # point to file containing header info for multifile systems
                raw_fname = raw_fname.replace('.eeg', '.vhdr')
                raw_fname = raw_fname.replace('.fdt', '.set')
                raw_fname = raw_fname.replace('.dat', '.lay')
                _, ext = _parse_ext(raw_fname)

                datatype = _handle_datatype(raw,None)
                bids_path = bids_path.copy()
                bids_path = bids_path.update(
                    datatype=datatype, suffix=datatype, extension=ext)

        update_dataset_description(rules__.get('dataset_description',{}),bids_path.root,do_not_create=write)
        rules__['IO']={}
        rules__['IO']['target'] = bids_path.fpath.__str__()
        rules__['IO']['source'] = f

        # POST-PROCESSING. For stuff easier to overwrite in the files rather than in the raw object
        # Rules that need to be applied to the result of mne-bids
        # Or maybe we should add the functionality directly to mne-bids
        if write or preview:
            # sidecar
            try:
                sidecar_path = bids_path.copy().update(datatype='eeg',suffix='eeg', extension='.json')
                with open(sidecar_path.fpath) as f:
                    sidecarjson = json.load(f)
                    sidecar = rules__.get('sidecar',{})
                    #TODO Validate the sidecar rules so as not to include dangerous stuff??
                    sidecarjson.update(sidecar)
                    sidecarjson.update({'RecordingDuration':real_times}) # needed if preview,since we crop
                    # maybe include an overwrite rule
                _write_json(sidecar_path.fpath,sidecarjson,overwrite=True)
                with open(sidecar_path.fpath) as f:
                    sidecarjson = f.read().replace('\n', '')
            except:
                sidecarjson = ''
            # channels
            channels_path = bids_path.copy().update(datatype='eeg',suffix='channels', extension='.tsv')
            try:
                channels_table = read_csv (channels_path.fpath, sep = '\t',dtype=str,keep_default_na=False,na_filter=False,na_values=[],true_values=[],false_values=[])
                channels_rules = rules__.get('channels',{})
                if 'type' in channels_rules: # types are post since they are not saved in vhdr (are they in edf??)
                    for ch_name,ch_type in channels_rules['type'].items():
                        channels_table.loc[(channels_table.name==str(ch_name)),'type'] = ch_type
                channels_table.to_csv(channels_path.fpath, index=False,sep='\t')
                with open(channels_path.fpath) as f:
                    channels = f.read().replace('\n', '__').replace('\t',',')
                chans_dict = channels_table.to_dict(orient='list')
                channels={}
                for key,value in chans_dict.items():
                     channels[str(key)] = ','.join(value)
            except:
                channels = ''
            # dataset_description
            daset_path = os.path.join(bids_path.root, 'dataset_description.json')
            if os.path.isfile(daset_path):
                with open(daset_path) as f:
                    #dasetjson = json.load(f)
                    #daset = rules__.get('dataset_description',{}) #TODO more work needed to overwrite, specifically fields which arent pure strings like authors
                    #TODO Validate the sidecar rules__ so as not to include dangerous stuff??
                    #dasetjson.update(daset)
                    # maybe include an overwrite rule
                    #if write:
                    #    _write_json(daset_path.fpath,dasetjson,overwrite=True)
                    dasetjson = f.read().replace('\n', '')
            else:
                dasetjson =''
    if preview:
        preview = {
            'IO' : rules__.get('IO',{}),
            'entities':rules__.get('entities',{}),
            'dataset_description':dasetjson,
            'sidecar':sidecarjson,
            'channels':channels,
            }
    #TODO remove general information of the dataset from the INDIVIDUAL MAPPINGS (ie dataset_description stuff)
    
    # CLEAN FILES IF NOT WRITE
    if not write and preview:
        new_files = _get_files(bids_path.root)
        new_files = list(set(new_files)-set(orig_files))
        for filename in new_files:
            if os.path.exists(filename): os.remove(filename)
    mapping = rules__
    if 'dataset_description' in rules__:
        del rules__['dataset_description']
    return mapping,preview
def apply_rules(source_path,bids_path,rules,mapping_path=''):
    """Apply rules to all the accepted files in a source path.

    Parameters
    ----------

    source_path : str | list of str
        If str, the path with the files we want to convert to bids.
        If list of str with the paths of the files we want to convert (ie the output of get_files).
    bids_path : str
        The path we want the converted files in.
    rules : str|dict
        The path to the rules file, or a dictionary with the rules.
    mapping_path : str, optional
        The fullpath where we want to write the mappings file.
        If '', then bids_path/code/sovabids/mappings.yml will be used.
    
    Returns
    -------

    mapping_data : dict
        A dictionary following: {'General': rules given,'Individual':list of mapping dictionaries for each file}
    """
    rules_ = load_rules(rules)

    if isinstance(source_path,str):
        filepaths = get_files(source_path,rules_)
    elif isinstance(source_path,list) and len(source_path)!= 0 and isinstance(source_path[0],str):
        filepaths = deepcopy(source_path)
    else:
        raise ValueError('The source_path should be either str or a non-empty list of str.')

    #%% BIDS CONVERSION
    all_mappings = []
    for f in filepaths:
        rules__,_ = apply_rules_to_single_file(f,rules_,bids_path,write=False,preview=False) #TODO There should be a way to control how verbose this is
        all_mappings.append(rules__)
    
    outputfolder,outputname = os.path.split(mapping_path)
    if outputname == '':
        outputname = 'mappings.yml'
    if outputfolder == '':
        outputfolder = os.path.join(bids_path,'code','sovabids')
    os.makedirs(outputfolder,exist_ok=True)
    full_rules_path = os.path.join(outputfolder,outputname)

    # ADD IO to General Rules (this is for the mapping file)
    rules_['IO'] = {}
    rules_['IO']['source'] = source_path
    rules_['IO']['target'] = bids_path
    mapping_data = {'General':rules_,'Individual':all_mappings}
    with open(full_rules_path, 'w') as outfile:
        yaml.dump(mapping_data, outfile, default_flow_style=False)

    print('Mapping file wrote to:',full_rules_path) #TODO This should be a log print
    return mapping_data

def sovapply():
    """Console script usage for applying rules."""
    # see https://github.com/Donders-Institute/bidscoin/blob/master/bidscoin/bidsmapper.py for example of how to make this
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser = subparsers.add_parser('apply_rules')
    parser.add_argument('source_path',help='The path to the input data directory that will be converted to bids')  # add the name argument
    parser.add_argument('bids_path',help='The path to the output bids directory')  # add the name argument
    parser.add_argument('rules',help='The fullpath of the rules file')  # add the name argument
    parser.add_argument('-m','--mapping', help='The fullpath of the mapping file to be written. If not set it will be located in bids_path/code/sovabids/mappings.yml',default='')
    args = parser.parse_args()
    apply_rules(args.source_path,args.bids_path,args.rules,args.mapping)

if __name__ == "__main__":
    sovapply()