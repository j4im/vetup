from flask import Flask, render_template, request, url_for
import elasticsearch
import math
from flask_wtf.csrf import CSRFProtect
from typing import List
from werkzeug.datastructures import MultiDict
import os

import logcheck
import vulogging

logger = vulogging.getLogger("vetup")

app = Flask(__name__)
app.config['SECRET_KEY'] = '1966e49d8454d0cd287cd9d0ba799d4abd6e44c09a39b721'
csrf = CSRFProtect(app) # FIXME - I doubt this is doing anything right now

MAX_QUERY_LEN = 256
RESULTS_PER_PAGE = 50
INDEX = 'vets'

class SearchParams:    
    SERVICES = ['AF', 'ARMY', 'CG', 'NAVY', 'USMC']
    BOARDS = ['DRB', 'BCMR', 'BCNR', 'PDBR']
    APPROVED = ['A', 'D']
    MIN_YEAR = 1980
    MAX_YEAR = 2015

    def __init__(self, args=MultiDict()):
        self.validate(args)
        
    def validate(self, args):
        # max length of 256 isn't based on anything known, just reasonableness
        self.query = args.get('q', '')[:MAX_QUERY_LEN]
        
        self.services = [x for x in args.getlist('services') if x in SearchParams.SERVICES]

        self.approved = [x for x in args.getlist('approved') if x in SearchParams.APPROVED]
        
        self.boards = [x for x in args.getlist('boards') if x in SearchParams.BOARDS]
        
        # BCNR is the navy equivalent of BCMR; user search form only has the latter
        if 'BCMR' in self.boards: 
            self.boards.append('BCNR')

        self.years = []
        for year_str in args.getlist('years'):
            try: 
                year = int(year_str)
                if (year >= SearchParams.MIN_YEAR and year <= SearchParams.MAX_YEAR):
                    self.years.append(year)
                else:
                    logger.error("received year out of range {}".format(year)) 
            except ValueError:
                logger.error("received invalid year {}".format(year_str))

        self.page = args.get('page', '0')
        try:
            self.page = int(self.page)
        except ValueError:
            self.page = 0

    
@app.route("/vetup/")
def home():
    logger.info("Requesting home")
    es_host = os.environ['ELASTICSEARCH_URL']

    es = elasticsearch.Elasticsearch(es_host)    

    search = {
        "size": 0,
        "aggs" : {
            "paths": {
                "composite" : {
                    "size": 1000,
                    "sources" : [
                        { "path": { "terms": {"field": "path" } } }
                    ]
                }
            }
        }
    }
    results = es.search(index=INDEX, body=search)

    paths = [(x['key']['path'], x['doc_count']) for x in results['aggregations']['paths']['buckets']]
    paths.sort(key = lambda x: x[0])
    
    path_tree = {'count': 0, 'children': {}}
    for path in paths:
        parent = path_tree
        for (i, elem) in enumerate(path[0].split("/")):
            if elem not in parent['children']:
                parent['children'][elem] = {'count': path[1], 'children': {}}
            parent['count'] += path[1]
            parent = parent['children'][elem]
    
    stats = get_statistics(es)
    
    return render_template("home.html", paths=paths, path_tree=path_tree, sp=SearchParams(), stats=stats)


def get_statistics(es):
    query = {
        "size": 0,
        "aggs": {
        }
    }
    
    for ext in ('TOTAL', 'doc', 'docx', 'pdf', 'rtf', 'txt'):
        if ext == 'TOTAL':
            wildcard = ''
        else:
            wildcard = '.' + ext
        agg = {
            "filter": {
                "wildcard": {
                    "raw_data_filename": {
                        "value": f"*{wildcard}"
                    }
                }
            },
            "aggs": {
                "has_text": {
                    "filter": {
                        "exists": {
                            "field": "text"
                        }
                    }
                },
                "has_summary": {
                    "filter": {
                        "exists": {
                            "field": "summary"
                        }
                    }
                }
            }
        }
        query['aggs'][ext] = agg
    
    results = es.search(index=INDEX, body=query)
    
    for ext in results['aggregations']:
        doc_count = results['aggregations'][ext].get('doc_count',0)
        
        for stat in ('has_text','has_summary'):
            if (doc_count > 0):
                num = results['aggregations'][ext][stat]['doc_count']
                percent = "({:.1%})".format(num / doc_count)
            else:
                percent = ''
            results['aggregations'][ext][stat]['percent'] = percent
    
    results
    return results['aggregations']


@app.route("/vetup/search/")
def search():
    logger.info("Searching with query: {}".format(str(request.args)))
    es_host = os.environ['ELASTICSEARCH_URL']

    es = elasticsearch.Elasticsearch(es_host)    

    start = 0

    sp = SearchParams(request.args)
    results_from = sp.page * RESULTS_PER_PAGE

    search = construct_search_query(sp, results_from)
    
    results = es.search(index=INDEX, body=search)
    
    total_hits = int(results['hits']['total']['value'])
    max_page = max(math.ceil(total_hits / RESULTS_PER_PAGE) - 1, 0)
    if (sp.page > max_page): sp.page = max_page

    pagination = {
        'max_page': max_page,
        'current_page': sp.page,
        'results_from': results_from+1,
        'results_to': results_from+len(results['hits']['hits']),
        'results_total': total_hits,
        'href_first': url_for(request.endpoint, q=sp.query, years=sp.years, boards=sp.boards, services=sp.services, approved=sp.approved, page=0),
        'href_prev': url_for(request.endpoint, q=sp.query, years=sp.years, boards=sp.boards, services=sp.services, approved=sp.approved, page=sp.page - 1),
        'href_next': url_for(request.endpoint, q=sp.query, years=sp.years, boards=sp.boards, services=sp.services, approved=sp.approved, page=sp.page + 1),
        'href_last': url_for(request.endpoint, q=sp.query, years=sp.years, boards=sp.boards, services=sp.services, approved=sp.approved, page=max_page)
    }

    for result in results['hits']['hits']:
        result['source'] = result['_source']

    title = "Search Results"
    return render_template("browse.html", sp=sp, title=title, results=results, pagination=pagination)



def construct_search_query(sp, results_from):
    
    search = {
        "from": results_from,
        "size": RESULTS_PER_PAGE,
        "query": {
            "bool": {
                "must": {
                    "simple_query_string": {
                        "fields": ["text"],
                        "query": sp.query
                    }
                }
            }
        },
        "highlight": {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "encoder": "html",
            "fields": { 
                "text": {
                    "highlight_query": {
                        "simple_query_string": {
                            
                            "fields": ["text"],
                            
                            "query": sp.query
                            
                        }                
                    }
                } 
            }
        }
    }
    
    # The issue is that all BCNR records are classified as "Navy"; so if the
    # user is searching for Marine (and not Navy) records within the BCNR, we
    # need include Navy results.  In this case we add a bonus to items that include 
    # the terms "usmc" or "marine" in the text 

    if ("USMC" in sp.services and "NAVY" not in sp.services): 
        if ("BCNR" in sp.boards or len(sp.boards) == 0):
            sp.services.append("NAVY")
            search['query']['bool']['should'] = {
                "match": {
                    "text": "usmc marine"
                }
            }
                
    
    filter = []
    if len(sp.services) > 0:
        filter.append({
            "terms": {
                "service": sp.services
            }
        })
    if len(sp.boards) > 0:
        filter.append({
            "terms": {
                "board": sp.boards
            }
        })
    if len(sp.years) > 0:
        filter.append({
            "terms": {
                "year": sp.years
            }
        })
    if len(sp.approved) > 0:
        filter.append({
            "terms": {
                "approved": sp.approved
            }
        })
    
    if len(filter) > 0:
        search['query']['bool']['filter'] = filter
    
    return search

@app.route("/vetup/browse/<service>/<board>/<time_period>/")
def browse(service, board, time_period):
    es_host = os.environ['ELASTICSEARCH_URL']

    es = elasticsearch.Elasticsearch(es_host)    

    start = 0

    path = "/".join([service,board,time_period])
    current_page = request.args.get('page', '0')
    try:
        current_page = int(current_page)
    except ValueError:
        current_page = 0
    
    results_from = current_page * RESULTS_PER_PAGE
    
    search = {
        "from": results_from,
        "size": RESULTS_PER_PAGE,
        "query": {
            "bool": {
                "filter": [
                    {"prefix": {"path": {"value": path}}}
                ]
            }
        },
        "sort": {"name": {"order": "asc"}}
    }
    
    results = es.search(index=INDEX, body=search)
    
    total_hits = int(results['hits']['total']['value'])
    max_page = math.ceil(total_hits / RESULTS_PER_PAGE) - 1
    if (current_page > max_page): current_page = max_page

    pagination = {
        'max_page': max_page,
        'current_page': current_page,
        'results_from': results_from+1,
        'results_to': results_from+len(results['hits']['hits']),
        'results_total': total_hits,
        'href_first': url_for(request.endpoint, **request.view_args, page=0),
        'href_prev': url_for(request.endpoint, **request.view_args, page=current_page - 1),
        'href_next': url_for(request.endpoint, **request.view_args, page=current_page + 1),
        'href_last': url_for(request.endpoint, **request.view_args, page=max_page)
    }

    for result in results['hits']['hits']:
        result['source'] = result['_source']
#        result['ext'] = Path(result['source'].get('raw_data_filename', '')).suffix
    title = " / ".join([service, board, time_period])
    
    
    return render_template("browse.html", title=title, results=results, pagination=pagination, sp=SearchParams())


def get_more_like_this(doc_id, es, index=INDEX, min_doc_freq=5):
    query = {
        "size": 10, 
        "query": {
            "more_like_this": {
                "fields": [
                    "text"
                ],
                "like": {
                    "_index":  index,
                    "_id": doc_id
                },
                "min_doc_freq": min_doc_freq
            }
        }
    }
    print(query)
    results = es.search(index=index, body=query)
    for result in results['hits']['hits']:
        result['source'] = result['_source']
    
    return results

@app.route("/vetup/detail/<path:path>/<name>")
def detail(path, name):
    es_host = os.environ['ELASTICSEARCH_URL']
    es = elasticsearch.Elasticsearch(es_host)    

    
    search = {
        "size": 1,
        "query": {
            "bool": {
                "filter": [
                    {"prefix": {"path": {"value": path}}},
                    {"term": {"name": {"value": name}}}
                ]
            }
        }
    }
    
    results = es.search(index=INDEX, body=search)
    
    if len(results['hits']['hits']) > 0:
        result = results['hits']['hits'][0]
        result['source'] = result['_source']
        more_like = get_more_like_this(result['_id'], es)
    else:
        logger.error(f"No results for detail view on path: {path} / name:{name}")
        result = None

    
    return render_template("detail.html", result=result, sp=SearchParams(), more_like=more_like)
    
@app.route("/vetup/status")
def status():
    msgs = logcheck.check_logs()
    return render_template("status.html", msgs=msgs)

if __name__ == "__main__":
    app.run(host='0.0.0.0')
