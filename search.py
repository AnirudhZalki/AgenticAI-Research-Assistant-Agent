import json
import os

class SearchTools:
    def __init__(self):
        # Load the mock databases
        base_dir = os.path.dirname(__file__)
        with open(os.path.join(base_dir, 'data/corpus.json'), 'r') as f:
            self.corpus = json.load(f)
        with open(os.path.join(base_dir, 'data/library.json'), 'r') as f:
            self.library = json.load(f)

    def read_corpus(self, keyword):
        # Returns papers that match the keyword in the title
        return [p for p in self.corpus if keyword.lower() in p['title'].lower()]

    def read_library(self):
        # Returns the researcher's past library
        return self.library