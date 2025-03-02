"""sovareject tests
Run tests:
>>> pytest

Run coverage
>>> coverage run -m pytest

Basic coverage reports
>>> coverage report 

HTML coverage reports
>>> coverage html

For debugging:
    Remove fixtures from functions
    (since fixtures cannot be called directly)
    and use the functions directly
In example:
>>> test_eegthresh(rej_matrix_tuple())
"""
from sovabids.parsers import parse_from_placeholder,parse_from_regex

def test_parse_from_regex():
    string = r'Y:\code\sovabids\_data\lemon2\sub-010002\ses-001\resting\sub-010002.vhdr'
    path_pattern = '.*?\\/.*?\\/.*?\\/.*?\\/.*?\\/sub-(.*?)\\/ses-(.*?)\\/(.*?)\\/sub-(.*?).vhdr'
    fields = ['ignore','entities.session','entities.task','entities.subject']
    result = parse_from_regex(string,path_pattern,fields)
    assert result['entities']['subject'] == '010002'
    assert result['entities']['session']=='001'
    assert result['entities']['task']=='resting'
    assert result['ignore']=='010002'

    string = r'Y:\code\sovabids\_data\lemon2\sub-010004\ses-001\sub-010004.vhdr'

    path_pattern = 'ses-(.*?)\\/s(.*?)-(.*?).vhdr'
    fields = ['entities.session','ignore','entities.subject']
    result = parse_from_regex(string,path_pattern,fields)
    assert result['entities']['session']=='001'
    assert result['entities']['subject']=='010004'
    assert result['ignore']=='ub'
    
    string = 'y:\\code\\sovabids\\_data\\lemon\\sub-010002.vhdr'
    path_pattern = 'sub-(.*?).vhdr'
    fields = 'entities.subject'
    result = parse_from_regex(string,path_pattern,fields)
    assert result['entities']['subject'] == '010002'

    path_pattern = '(.*?)\\/sub-(.*?).vhdr'
    fields = ['ignore','entities.subject']
    result = parse_from_regex(string,path_pattern,fields)
    assert result['entities']['subject'] == '010002'
    assert result['ignore'] == 'y:/code/sovabids/_data/lemon' #USE POSIX

    path_pattern = '(.*?).vhdr'
    fields = 'entities.subject'
    result = parse_from_regex(string,path_pattern,fields)
    assert result['entities']['subject'] == 'y:/code/sovabids/_data/lemon/sub-010002'

    path_pattern = 'sub-(.*)' # notice no "?",or use .+
    fields = 'entities.subject'
    result = parse_from_regex(string,path_pattern,fields)
    assert result['entities']['subject'] == '010002.vhdr'


def test_parse_from_placeholder():
    matcher = '(.+)'
    string = r'Y:\code\sovabids\_data\lemon2\sub-010002\ses-001\resting\sub-010002.vhdr'
    path_pattern = 'sub-%ignore%\ses-%entities.session%\%entities.task%\sub-%entities.subject%.vhdr'
    result = parse_from_placeholder(string,path_pattern,matcher=matcher)
    assert result['entities']['subject'] == '010002'
    assert result['entities']['session']=='001'
    assert result['entities']['task']=='resting'
    assert result['ignore']=='010002'

    string = r'Y:\code\sovabids\_data\lemon2\sub-010004\ses-001\sub-010004.vhdr'
    path_pattern = 'ses-%entities.session%/s%ignore%-%entities.subject%.vhdr'
    result = parse_from_placeholder(string,path_pattern,matcher=matcher)
    assert result['entities']['session']=='001'
    assert result['entities']['subject']=='010004'
    assert result['ignore']=='ub'
    
    string = 'y:\\code\\sovabids\\_data\\lemon\\sub-010002.vhdr'
    path_pattern = 'sub-%entities.subject%.vhdr'
    result = parse_from_placeholder(string,path_pattern,matcher=matcher)
    assert result['entities']['subject'] == '010002'

    path_pattern = '%ignore%\sub-%entities.subject%.vhdr'
    result = parse_from_placeholder(string,path_pattern,matcher=matcher)
    assert result['entities']['subject'] == '010002'
    assert result['ignore'] == 'y:/code/sovabids/_data/lemon' #USE POSIX

    path_pattern = '%entities.subject%.vhdr'
    result = parse_from_placeholder(string,path_pattern,matcher=matcher)
    assert result['entities']['subject'] == 'y:/code/sovabids/_data/lemon/sub-010002'

    path_pattern = 'sub-%entities.subject%'
    result = parse_from_placeholder(string,path_pattern,matcher=matcher)
    assert result['entities']['subject'] == '010002.vhdr'


if __name__ == '__main__':
    test_parse_from_regex()
    test_parse_from_placeholder()
    print('ok')