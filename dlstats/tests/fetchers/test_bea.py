# -*- coding: utf-8 -*-

import io
import os

from dlstats.fetchers.bea import BEA as Fetcher

import httpretty

from dlstats.tests.base import RESOURCES_DIR as BASE_RESOURCES_DIR
from dlstats.tests.fetchers.base import BaseFetcherTestCase

import unittest
from unittest import mock

RESOURCES_DIR = os.path.abspath(os.path.join(BASE_RESOURCES_DIR, "bea"))

DATA_BEA_10101_An = {
    "filepath": os.path.abspath(os.path.join(RESOURCES_DIR, "nipa-section1.xls.zip")),
    "DSD": {
        "provider": "BEA",
        "filepath": None,
        "dataset_code": "nipa-section1-10101-a",
        "dsd_id": "nipa-section1-10101-a",
        "is_completed": True,
        "categories_key": "nipa-section1",
        "categories_parents": ["national", "nipa"],
        "categories_root": ["national", "nipa", "nipa-fa2004", "nipa-underlying"],
        "concept_keys": ['concept', 'frequency'],
        "codelist_keys": ['concept', 'frequency'],
        "codelist_count": {
            "concept": 25,
            "frequency": 1
        },        
        "dimension_keys": ['concept', 'frequency'],
        "dimension_count": {
            "concept": 25,
            "frequency": 1
        },
        "attribute_keys": [],
        "attribute_count": None,
    },
    "series_accept": 25,
    "series_reject_frequency": 0,
    "series_reject_empty": 0,
    "series_all_values": 1175,
    "series_key_first": "A191RL1-A",
    "series_key_last": "A191RP1-A",
    "series_sample": {
        'provider_name': 'BEA',
        'dataset_code': 'nipa-section1-10101-a',
        'key': 'A191RL1-A',
        'name': 'Gross domestic product - Annually',
        'frequency': 'A',
        'last_update': None,
        'first_value': {
            'value': '3.1',
            'ordinal': -1,
            'period': '1969',
            'attributes': None,
        },
        'last_value': {
            'value': '2.4',
            'ordinal': 45,
            'period': '2015',
            'attributes': None,
        },
        'dimensions': {
            'concept': 'a191rl1',
            "frequency": 'a'
        },
        'attributes': None,
    }
}

def _get_datasets_settings(self):
    return { 
        "nipa-section1-10101-a": {
            'dataset_code': 'nipa-section1-10101-a',
            'name': 'Table 1.1.1. Percent Change From Preceding Period in Real Gross Domestic Product - Annually',
            'last_update': None,
            'metadata': {
                'filename': 'nipa-section1.xls.zip',
                'sheet_name': '10101 Ann',
                'url': 'http://www.bea.gov/national/nipaweb/GetCSV.asp?GetWhat=SS_Data/Section1All_xls.zip&Section=2'
            },
        }
    }

class FetcherTestCase(BaseFetcherTestCase):

    # nosetests -s -v dlstats.tests.fetchers.test_bea:FetcherTestCase
    
    FETCHER_KLASS = Fetcher
    
    DATASETS = {
        'nipa-section1-10101-a': DATA_BEA_10101_An
    }
    
    DATASET_FIRST = "nipa-fa2004-section1-101-a"
    DATASET_LAST = "nipa-underlying-section9-90500U-a"
    DEBUG_MODE = False

    def _load_files(self, dataset_code):
        url = "http://www.bea.gov/national/nipaweb/GetCSV.asp?GetWhat=SS_Data/Section1All_xls.zip&Section=2"
        self.register_url(url, 
                          self.DATASETS[dataset_code]["filepath"])

    @httpretty.activate
    @unittest.skipUnless('FULL_TEST' in os.environ, "Skip - no full test")
    def test_load_datasets_first(self):

        dataset_code = "nipa-section1-10101-a"
        self._load_files(dataset_code)
        self.assertLoadDatasetsFirst([dataset_code])

    @httpretty.activate     
    @unittest.skipUnless('FULL_TEST' in os.environ, "Skip - no full test")
    def test_load_datasets_update(self):

        dataset_code = "nipa-section1-10101-a"
        self._load_files(dataset_code)
        self.assertLoadDatasetsUpdate([dataset_code])

    #@httpretty.activate
    @unittest.skipIf(True, "TODO")     
    def test_build_data_tree(self):

        dataset_code = "nipa-section1-10101-a"
        self.assertDataTree(dataset_code)
            
    @httpretty.activate
    @mock.patch("dlstats.fetchers.bea.BEA._get_datasets_settings", _get_datasets_settings)     
    def test_upsert_dataset_10101(self):

        # nosetests -s -v dlstats.tests.fetchers.test_bea:FetcherTestCase.test_upsert_dataset_10101
    
        dataset_code = "nipa-section1-10101-a"
        
        self._load_files(dataset_code)
    
        self.assertProvider()
        self.assertDataset(dataset_code)        
        self.assertSeries(dataset_code)

