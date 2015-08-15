#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
.. module:: _skeleton
    :synopsis: Module containing an abstract base class for all the fetchers
"""
import pymongo
import datetime
import pandas
from voluptuous import Required, All, Length, Range, Schema, Invalid, Object, Optional, Any, Extra
from dlstats import configuration
#from dlstats.misc_func import dictionary_union
#from ..misc_func import dictionary_union
from datetime import datetime
import logging
import bson
import pprint
from collections import defaultdict
from dlstats import mongo_client

class Skeleton(object):
    """Abstract base class for fetchers"""
    def __init__(self, provider_name=None):
        self.configuration = configuration
        self.provider_name = provider_name
        self.db = mongo_client.widukind

    def upsert_categories(self,id):
        """Upsert the categories in MongoDB
        """
        raise NotImplementedError("This method from the Skeleton class must"
                                  "be implemented.")
    def upsert_series(self):
        """Upsert all the series in MongoDB
        """
        raise NotImplementedError("This method from the Skeleton class must"
                                  "be implemented.")
    def upsert_a_series(self,id):
        """Upsert the series in MongoDB
        """
        raise NotImplementedError("This method from the Skeleton class must"
                                  "be implemented.")
    def upsert_dataset(self,id):
        """Upsert a dataset in MongoDB
        """
        raise NotImplementedError("This method from the Skeleton class must"
                                  "be implemented.")
    def insert_provider(self):
        """Insert the provider in MongoDB
        """
        self.provider.update_database()

#Validation and ODM
#Custom validator (only a few types are natively implemented in voluptuous)
def date_validator(value):
    if isinstance(value, datetime):
        return value
    else:
        raise Invalid('Input date was not of type datetime')

def typecheck(type, msg=None):
    """Coerce a value to a type.

    If the type constructor throws a ValueError, the value will be marked as
    Invalid.
    """
    def validator(value):
        if not isinstance(value,type):
            raise Invalid(msg or ('expected %s' % type.__name__))
        else:
            return value
    return validator


#Schema definition in voluptuous
revision_schema = [{Required('value'): Any(str), Required('position'): int,
             Required('releaseDates'): [date_validator]}]
dimensions = {str: str}
attributes = {str: [str]}
attribute_list_schema = {str: [(str,str)]}
dimension_list_schema = {str: [All()]}

class DlstatsCollection(object):
    """Abstract base class for objects that are stored and indexed by dlstats
    """
    def __init__(self):
        self.db = mongo_client.widukind
        self.testing_mode = False
        
class Provider(DlstatsCollection):
    """Abstract base class for providers
    >>> provider = Provider(name='Eurostat',website='http://ec.europa.eu/eurostat')
    >>> print(provider)
    [('name', 'Eurostat'), ('website', 'http://ec.europa.eu/eurostat')]
    >>>
    """

    def __init__(self,
                 name=None,
                 website=None):
        super().__init__()
        self.configuration=configuration
        self.name=name
        self.website=website

        self.schema = Schema({'name':
                              All(str, Length(min=1)),
                              'website':
                              All(str, Length(min=9))
                             },required=True)

        self.validate = self.schema({'name': self.name,
                                     'website': self.website
                                 })
        
    def __repr__(self):
        return pprint.pformat([(key, self.validate[key]) for key in sorted(self.validate.keys())])

    @property
    def bson(self):
        return {'name': self.name,
                'website': self.website}

    def update_database(self,mongo_id=None,key=None):
        if not self.testing_mode:
            return self.db.providers.update({'name':self.bson['name']},self.bson,upsert=True)

class Series(DlstatsCollection):
    """Abstract base class for time series
    >>> dataset = Dataset(provider_name='Test provider',
    ...                   dataset_code='nama_gdp_fr')
    >>> series = Series(dataset)
    >>> print(series)
    [('attributes', {'OBS_VALUE': ['p']}),
     ('datasetCode', 'nama_gdp_fr'),
     ('dimensions', {'Seasonal adjustment': 'wda'}),
     ('key', 'GDP_FR'),
     ('name', 'GDP in France'),
     ('period_index',
      <class 'pandas.tseries.period.PeriodIndex'>
    [1999Q1, ..., 2016Q4]
    Length: 72, Freq: Q-DEC),
     ('provider', 'Test provider'),
     ('releaseDates',
      [datetime.datetime(2013, 11, 28, 0, 0),
       datetime.datetime(2014, 12, 28, 0, 0),
       datetime.datetime(2015, 1, 28, 0, 0),
       datetime.datetime(2015, 2, 28, 0, 0)]),
     ('revisions',
      [{'position': 2,
        'releaseDates': [datetime.datetime(2014, 11, 28, 0, 0)],
        'value': '2710'}]),
     ('values', ['2700', '2720', '2740', '2760'])]
    >>>
    """

    def __init__(self,provider_name,dataset_code,last_update,bulk_size=1000):
        super().__init__()
        self.provider_name = provider_name
        self.dataset_code = dataset_code
        self.last_update = last_update
        self.bulk_size = bulk_size
        self.ser_list = []
        self.schema = Schema({'name':
                              All(str, Length(min=1)),
                              'provider':
                              All(str, Length(min=1)),
                              'key':
                              All(str, Length(min=1)),
                              'datasetCode':
                              All(str, Length(min=1)),
                              'startDate':
                              date_validator,
                              'endDate':
                              date_validator,
                              'values':
                              [Any(str)],
                              'releaseDates':
                              [date_validator],
                              'attributes':
                              Any({},attributes),
                              'revisions':
                              Any(None,revision_schema),
                              'dimensions':
                              dimensions,
                              'frequency': 
                              All(str, Length(min=1)),
                              Optional('notes'):
                              str
                             },required=True)

    def set_data_iterator(self,data_iterator):
        self.data_iterator = data_iterator

    def process_series(self):
        count = 0
        while True:
            try:
                self.ser_list.append( next(self.data_iterator))
            except StopIteration:
                break
            count += 1
            if count > self.bulk_size:
                self.update_series_list()
                count = 0
        if count > 0:
            self.update_series_list()
        
    def update_series_list(self):
        keys = [s['key'] for s in self.ser_list]
        old_series = self.db.series.find({'provider': self.provider_name, 'datasetCode': self.dataset_code, 'key': {'$in': keys}})
        old_series = {s['key']:s for s in old_series}
        bulk = self.db.series.initialize_ordered_bulk_op()
        for bson in self.ser_list:
            period_index = bson.pop('period_index')
            bson['startDate'] = period_index[0].to_timestamp()
            bson['endDate'] = period_index[-1].to_timestamp()
            self.schema(bson)
            if bson['key'] not in old_series:
                bulk.insert(bson)
            else:
                old_bson = old_series[bson['key']]
                position = 0
                bson['revisions'] = old_bson['revisions']
                old_start_period = pandas.Period(
                    old_bson['startDate'],freq=old_bson['frequency'])
                start_period = pandas.Period(
                    bson['startDate'],freq=bson['frequency'])
                if bson['revisions'] is None:
                    bson['revisions'] = []
                    if start_period > old_start_period:
                        # previous, longer, series is kept
                        offset = start_period - old_start_period
                        bson['numberOfPeriods'] += offset
                        bson['startDate'] = old_bson['startDate']
                        for values in zip(old_bson['values'][offset:],bson['values']):
                            if values[0] != values[1]:
                                bson['revisions'].append(
                                    {'value':values[0],
                                     'position': offset+position,
                                     'releaseDates':
                                     old_bson['releaseDates'][offset+position]})
                            position += 1
                else:
                    # zero or more data are added at the beginning of the series
                    offset = old_start_period - start_period
                    for values in zip(old_bson['values'],bson['values'][offset:]):
                        if values[0] != values[1]:
                            bson['revisions'].append(
                                {'value':values[0],
                                 'position': offset+position,
                                 'releaseDates':
                                 old_bson['releaseDates'][position]})
                        position += 1
                bulk.find({'_id': old_bson['_id']}).update({'$set': bson})
        bulk.execute()
        self.ser_list = []
            
    def bulk_update_database(self):
        if not self.testing_mode:
            mdb_bulk = self.db.series.initialize_ordered_bulk_op()
            for s in self.data:
                s.collection = mdb_bulk
                s.update_database()
            return mdb_bulk.execute();

class CodeDict():
    def __init__(self,code_dict = {}):
        self.code_dict = code_dict
        self.schema = Schema({Extra: dict})
        self.schema(code_dict)
        
    def update(self,arg):
        self.schema(arg.code_dict)
        self.code_dict.update(arg.code_dict)
        
    def update_entry(self,dim_name,dim_short_id,dim_long_id):
        if dim_name in self.code_dict:
            if not dim_long_id:
                dim_short_id = 'None'
                if 'None' not in self.code_dict[dim_name]:
                    self.code_dict[dim_name].update({'None': 'None'})
            elif not dim_short_id:
                try:
                    dim_short_id = next(key for key,value in self.code_dict[dim_name].items() if value == dim_long_id)
                except StopIteration:
                    dim_short_id = str(len(self.code_dict[dim_name]))
                    self.code_dict[dim_name].update({dim_short_id: dim_long_id})
            elif not dim_short_id in self.code_dict[dim_name]:
                self.code_dict[dim_name].update({dim_short_id: dim_long_id})
        else:
            if not dim_short_id:
                dim_short_id = '0'
            self.code_dict[dim_name] = {dim_short_id: dim_long_id}
        return(dim_short_id)

    def get_dict(self):
        return(self.code_dict)
    
    def get_list(self):
        return({d: list(self.code_dict[d].items()) for d in self.code_dict})

    def set_from_list(self,dimension_list):
        self.code_dict = {d1: {d2[0]: d2[1] for d2 in dimension_list[d1]} for d1 in dimension_list}
    
class DatasetMB(DlstatsCollection):
    """Abstract base class for datasets
    >>> from datetime import datetime
    >>> dataset = DatasetMB(provider='Test provider',name='GDP in France',
    ...                 datasetCode='nama_gdp_fr',
    ...                 dimensionList={'name':[('CO','COUNTRY')],'values':[('FR','France'),('DE','Germany')]},
    ...                 attributeList={'OBS_VALUE': [('p', 'preliminary'), ('f', 'forecast')]},
    ...                 docHref='http://nauriset',
    ...                 lastUpdate=datetime(2014,12,2))
    >>> print(dataset)
    [('attributeList', {'OBS_VALUE': [('p', 'preliminary'), ('f', 'forecast')]}),
     ('datasetCode', 'nama_gdp_fr'),
     ('dimensionList',
      {'name': [('CO', 'COUNTRY')],
       'values': [('FR', 'France'), ('DE', 'Germany')]}),
     ('docHref', 'http://nauriset'),
     ('lastUpdate', datetime.datetime(2014, 12, 2, 0, 0)),
     ('name', 'GDP in France'),
     ('provider', 'Test provider')]
    """
    def __init__(self,
                 provider=None,
                 datasetCode=None,
                 name=None,
                 dimensionList=None,
                 attributeList=None,
                 docHref=None,
                 lastUpdate=None
                ):
        super().__init__()
        self.configuration=configuration
        self.provider=provider
        self.datasetCode=datasetCode
        self.name=name
        self.attributeList=attributeList
        self.dimensionList=dimensionList
        self.docHref=docHref
        self.lastUpdate=lastUpdate
        self.configuration = configuration
        self.schema = Schema({'name':
                              All(str, Length(min=1)),
                              'provider':
                              All(str, Length(min=1)),
                              'datasetCode':
                              All(str, Length(min=1)),
                              'docHref':
                              Any(None,str),
                              'lastUpdate':
                              typecheck(datetime),
                              'dimensionList':
                              dimension_list_schema,
                              'attributeList':
                              Any(None,attribute_list_schema)
                               },required=True)
        self.validate = self.schema({'provider': self.provider,
                                     'datasetCode': self.datasetCode,
                                     'name': self.name,
                                     'dimensionList': self.dimensionList,
                                     'attributeList': self.attributeList,
                                     'docHref': self.docHref,
                                     'lastUpdate': self.lastUpdate
        })

    def __repr__(self):
        return pprint.pformat([(key, self.validate[key])
                               for key in sorted(self.validate.keys())])

    @property
    def bson(self):
        return {'provider': self.provider,
                'name': self.name,
                'datasetCode': self.datasetCode,
                'dimensionList': self.dimensionList,
                'attributeList': self.attributeList,
                'docHref': self.docHref,
                'lastUpdate': self.lastUpdate}

    def update_database(self):
        if not self.testing_mode:
            self.db.datasets.update({'datasetCode': self.bson['datasetCode']},
                                    self.bson,upsert=True)

class Dataset(DlstatsCollection):
    def __init__(self,provider_name,dataset_code):
        super().__init__()
        self.provider_name = provider_name
        self.dataset_code = dataset_code
        self.name = None
        self.doc_href = None
        self.last_update = None
        self.dimension_list = CodeDict()
        self.attribute_list = CodeDict()
        self.load_previous_version(provider_name,dataset_code)
        self.schema = Schema({'name':
                              All(str, Length(min=1)),
                              'provider':
                              All(str, Length(min=1)),
                              'datasetCode':
                              All(str, Length(min=1)),
                              'docHref':
                              Any(None,str),
                              'lastUpdate':
                              typecheck(datetime),
                              'dimensionList':
                              dimension_list_schema,
                              'attributeList':
                              Any(None,attribute_list_schema)
                             },required=True)
        self.series = Series(self.provider_name,
                             self.dataset_code,
                             self.last_update)

    @property
    def bson(self):
        return {'provider': self.provider_name,
                'name': self.name,
                'datasetCode': self.dataset_code,
                'dimensionList': self.dimension_list.get_list(),
                'attributeList': self.attribute_list.get_list(),
                'docHref': self.doc_href,
                'lastUpdate': self.last_update}

    def load_previous_version(self,provider_name,dataset_code):
        dataset = self.db.datasets.find_one({'provider': provider_name,
                                             'datasetCode': dataset_code})
        if dataset:
            # convert to dict of dict
            self.dimension_list.set_from_list(dataset['dimensionList'])
            self.attribute_list.set_from_list(dataset['attributeList'])
        
    def update_database(self):
        self.series.process_series()
        self.db.datasets.update({'datasetCode': self.bson['datasetCode']},
                                self.bson,upsert=True)

class Category(DlstatsCollection):
    """Abstract base class for categories
    >>> from datetime import datetime
    >>> category = Category(provider='Test provider',name='GDP',
    ...                 categoryCode='nama_gdp',
    ...                 children=[bson.objectid.ObjectId.from_datetime(datetime(2014,12,3))],
    ...                 docHref='http://www.perdu.com',
    ...                 lastUpdate=datetime(2014,12,2),
    ...                 exposed=True)
    >>> print(category)
    [('categoryCode', 'nama_gdp'),
     ('children', [ObjectId('547e52800000000000000000')]),
     ('docHref', 'http://www.perdu.com'),
     ('exposed', True),
     ('lastUpdate', datetime.datetime(2014, 12, 2, 0, 0)),
     ('name', 'GDP'),
     ('provider', 'Test provider')]
    """
    def __init__(self,
                 provider=None,
                 name=None,
                 docHref=None,
                 children=None,
                 categoryCode=None,
                 lastUpdate=None,
                 exposed=False
                ):
        super().__init__()
        self.configuration = configuration
        self.provider=provider
        self.name=name
        self.docHref=docHref
        self.children=children
        self.categoryCode=categoryCode
        self.lastUpdate=lastUpdate
        self.exposed=exposed
        self.configuration=configuration
        self.schema = Schema({'name':
                              All(str, Length(min=1)),
                              'provider':
                              All(str, Length(min=1)),
                              'children':
                              Any(None,[typecheck(bson.objectid.ObjectId)]),
                              'docHref':
                              Any(None,str),
                              'lastUpdate':
                              Any(None,typecheck(datetime)),
                              'categoryCode':
                              All(str, Length(min=1)),
                              'exposed':
                              typecheck(bool)
                          }, required=True
)
        self.validate = self.schema({'provider': self.provider,
                    'categoryCode': self.categoryCode,
                    'name': self.name,
                    'children': self.children,
                    'docHref': self.docHref,
                    'lastUpdate': self.lastUpdate,
                    'exposed': self.exposed
                    })

    def __repr__(self):
        return pprint.pformat([(key, self.validate[key])
                               for key in sorted(self.validate.keys())])

    @property
    def bson(self):
        return {'provider': self.provider,
                'name': self.name,
                'docHref': self.docHref,
                'children': self.children,
                'categoryCode': self.categoryCode,
                'lastUpdate': self.lastUpdate,
                'exposed': self.exposed}
    def update_database(self):
        in_base_category = self.db.categories.find_one(
            {'categoryCode': self.bson['categoryCode']})
        if in_base_category is None:
  	     	_id_ = self.db.categories.insert(self.bson)
        else:
            self.db.categories.update(
                {'_id': in_base_category['_id']},self.bson)
            _id_ = in_base_category['_id']
        return _id_

class BulkSeries():
    def init(self):
        pass

if __name__ == "__main__":
    import doctest
    class Series(Series):
        def handle_one_series(self):
            return({'provider' : 'Test provider',
                    'name' : 'GDP in France',
                    'key' : 'GDP_FR',
                    'datasetCode' : 'nama_gdp_fr',
                    'values' : ['2700', '2720', '2740', '2760'],
                    'releaseDates' : [datetime(2013,11,28),datetime(2014,12,28),datetime(2015,1,28),datetime(2015,2,28)],
                    'period_index' : pandas.period_range('1/1999', periods=72, freq='Q'),
                    'attributes' : {'OBS_VALUE': ['p']},
                    'revisions' : [{'value': '2710', 'position':2,
                                    'releaseDates' : [datetime(2014,11,28)]}],
                    'dimensions' : [{'Seasonal adjustment':'wda'}]})
    doctest.testmod()
