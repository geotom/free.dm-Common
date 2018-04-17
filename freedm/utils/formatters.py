'''
Text formatting util methods
@author: Thomas Wanderer
'''

# Imports
import json
import textwrap
from typing import Dict, List, Any

class TableFormatter:
    '''
    A formatter printing data objects as formatted simple text table
    :param dict columns: A dictionary or py:class:::collections.OrderedDict of column keys (corresponding to the rowdata) and their responding header text
    :param list rowdata: A list of dictionaries where each dictionary stands for one row
    :param int distance: The minimum whitespace characters between each column (default = 4)
    :param int maxlength: The maximum character length of each column (default = 30)
    :param int indention: Optimal amount of whitespace characters by which the table gets indented (default = 0)
    '''
    keys = None
    widths = {}
    
    Row = Dict[str, str]
    
    def __init__(self, columns: Row, rowdata: List[Row], distance: int=4, maxlength: int=30, indention: int=0):
        try:
            # Save arguments
            self.columns    = columns
            self.data       = rowdata
            self.distance   = distance
            self.maxlength  = maxlength
            self.indention  = indention
            # Get the with of the column headers
            self.keys = columns.keys()
            for c in self.keys:
                self.widths.update({c: len(str(columns[c])) if len(str(columns[c])) < maxlength else maxlength})
            # Get the width from the data
            for item in rowdata:
                keys = item.keys()
                for k in keys:
                    if k in self.keys:
                        if len(str(item[k])) > self.widths[k]:
                            self.widths.update({k: len(str(item[k])) if len(str(item[k])) < maxlength else maxlength})
        except:
            pass
    
    def render(self) -> str:
        '''
        Renders and returns the data as formatted text table
        :returns: The formatted table
        :rtype: str
        '''
        # Add headers
        table = ('{:<' + str(self.indention) + '}').format('')
        for k in self.keys:
            table += ('{:<' + str(self.widths[k] + self.distance) + '}').format(self.columns[k])
        for item in self.data:
            row = ('\n{:<' + str(self.indention) + '}').format('')
            for k in self.keys:
                row += ('{:<' + str(self.widths[k] + self.distance) + '}').format(ellipsis(item[k], self.maxlength))
            table += row
        return table
    
def ellipsis(text, length: int) -> str:
    '''
    Truncates a too long string at the provided length and returns it together with an ellipsis
    :param str text: The text to truncate
    :param int length: The maximum length
    :returns text: The truncated text
    :rtype: str
    '''
    try:
        return textwrap.shorten(text, length, placeholder='...')
    except:
        return text
    
def printPrettyDict(data: dict) -> None:
    '''
    Prints a dictionary in a readable way with ordered keys
    '''
    print(json.dumps(data, indent=4 , sort_keys=True))
        