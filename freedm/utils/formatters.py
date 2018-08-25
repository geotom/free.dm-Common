'''
Text formatting utility methods
@author: Thomas Wanderer
'''

# Imports
import json
import textwrap
from typing import Dict, List

# Type aliases
Row = Dict[str, str]


class TableFormatter:
    '''
    A formatter printing data objects as formatted simple text table. Use a collection.OrderedDicts to preserve the sequence of the table columns
    '''
    keys = None
    widths = {}

    def __init__(self, columns: Row, rowdata: List[Row], distance: int=4, maxlength: int=30, indention: int=0):
        try:
            # Save arguments
            self.columns = columns
            self.data = rowdata
            self.distance = distance
            self.maxlength = maxlength
            self.indention = indention
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
        except Exception:
            pass

    def render(self) -> str:
        '''
        Renders and returns the data as formatted text table
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
    '''
    try:
        return textwrap.shorten(text, length, placeholder='...')
    except Exception:
        return text


def printPrettyDict(data: dict) -> None:
    '''
    Prints a dictionary in a readable way with ordered keys
    '''
    print(json.dumps(data, indent=4, sort_keys=True))
