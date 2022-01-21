from flask import Flask, request, Response, send_file
from flask_cors import CORS
import markdown2
import pygments
import time
import json
import hashlib
import pickle
import os

import constants as cnst

app = Flask(__name__)
CORS(app)
content_dict = None


@app.route("/projects", methods=["GET"])
def get_projects():
    return_json = {"projects": [content_dict.get(key) for key in content_dict.keys()]}
    return Response(json.dumps(return_json), status=200, mimetype='application/json')


@app.route("/projects", methods=["POST"])
def create_project():
    global content_dict
    template = cnst.project_dict.copy()
    template['title'] = request.json['data']['projectName'].strip()
    template['purpose'] = request.json['data']['projectPurpose'].strip()
    template['category'] = request.json['data']['projectCategory'].strip()
    template['creation_date'] = request.json['data']['projectCreationTime']
    prehash = template['title'] + str(template['creation_date'])
    template['id'] = hashlib.sha256(bytes(prehash, 'utf-8')).hexdigest()
    content_dict.update({template['id']: template})
    print(f'Received New Project {template["title"]}')
    save_data(content_dict)
    return Response("Okay", status=200, mimetype='application/json')


@app.route("/project", methods=["GET"])
def get_project():
    global content_dict
    project_id = request.args.get('id')
    project = content_dict.get(project_id)
    return_json = {"project": project}
    return Response(json.dumps(return_json), status=200, mimetype='application/json')


@app.route("/project", methods=["POST"])
def update_project():
    # TODO FINISHIS
    global content_dict
    project_id = request.args.get('id')
    project = content_dict.get(project_id)
    project['title'] = request.args.get('title')
    save_data(content_dict)
    return Response(json.dumps({'status': 'ok'}), status=200, mimetype='application/json')


@app.route("/delete", methods=["GET"])
def delete_project():
    global content_dict
    # back-up
    id_to_remove = request.args.get('id')
    if id_to_remove in content_dict.keys():
        content_dict.pop(id_to_remove)
    else:
        for key in content_dict.keys():
            project = content_dict.get(key)
            if id_to_remove in project['pages'].keys():
                project['pages'].pop(id_to_remove)
            for page_id in project['pages'].keys():
                page = project['pages'].get(page_id)
                if id_to_remove in page['code_snippets'].keys():
                    page['code_snippets'].pop(id_to_remove)
    # save
    return Response(id_to_remove, status=200, mimetype='application/json')


@app.route("/updates", methods=["GET"])
def send_current():
    parent_id = request.args.get('parentID')
    page_id = request.args.get('pageID')
    project = content_dict.get(parent_id)
    page = project['pages'].get(page_id)
    return_json = {
        "content": page['content'],
        'updateTime': page['lastUpdate']
    }
    return Response(json.dumps(return_json), status=200, mimetype='application/json')


@app.route("/updates", methods=["POST"])
def update_current():
    global content_dict
    div_content = request.json['data']['divContent']
    update_time = request.json['data']['time']
    parent_id = request.json['data']['parentID']
    page_id = request.json['data']['pageID']
    project = content_dict.get(parent_id)
    page = project['pages'].get(page_id)
    if int(update_time) > int(page['lastUpdate']):
        page['lastUpdate'] = update_time
        page['content'] = div_content
        print(f'Message update {div_content} at {update_time} for {page["title"]}')
        save_data(content_dict)
    return Response("Ok", status=200, mimetype='application/json')


@app.route("/pages", methods=["POST"])
def create_page():
    global content_dict
    template = cnst.page_dict.copy()
    template['title'] = request.json['data']['pageName'].strip()
    template['creation_date'] = request.json['data']['pageCreationTime']
    prehash = template['title'] + str(template['creation_date'])
    template['id'] = hashlib.sha256(bytes(prehash, 'utf-8')).hexdigest()
    parent_project = content_dict.get(request.json['data']['pageParent'])
    parent_project['pages'].update({template['id']: template})
    print(f'Received New Page {template["title"]} for  {parent_project["title"]}')
    save_data(content_dict)
    return Response("Okay", status=200, mimetype='application/json')


@app.route("/pages", methods=["GET"])
def get_pages():
    global content_dict
    parent_id = request.args.get('id')
    parent = content_dict.get(parent_id)
    pages_dict = parent['pages']
    return_json = {"pages": [pages_dict.get(key) for key in pages_dict.keys()]}
    return Response(json.dumps(return_json), status=200, mimetype='application/json')


@app.route("/page", methods=["GET"])
def get_page():
    global content_dict
    page = find_page(request.args.get("id"))
    return_json = {"page": page}
    return Response(json.dumps(return_json), status=200, mimetype='application/json')


@app.route("/images", methods=["POST"])
def save_image():
    file = request.files['image']
    prehash = str(time.time()) + file.filename
    file_name = hashlib.sha256(bytes(prehash, 'utf-8')).hexdigest()
    file.save(os.path.join(cnst.images, file_name + ".png"))
    print(file_name)
    print(len(file_name))
    return Response(json.dumps({'image': file_name}), status=200, mimetype='application/json')


@app.route("/images", methods=["GET"])
def get_image():
    image_name = request.args.get('image')
    return send_file(cnst.images + image_name + '.png', mimetype='image/png')


@app.route("/snippets", methods=['POST'])
def add_snippet():
    global content_dict
    page_id = request.json['data']['pageID']
    page = find_page(page_id)
    template = cnst.code_snippets_dict.copy()
    template['title'] = request.json['data']['title']
    template['description'] = request.json['data']['description']
    template['language'] = request.json['data']['language']
    template['raw'] = request.json['data']['code']
    prehash = template['title'] + str(template['creation_date'])
    template['id'] = hashlib.sha256(bytes(prehash, 'utf-8')).hexdigest()
    template['marked'] = markdown2.markdown(f"\n```{template['language']}\n{template['raw']}\n```",
                                            extras=['fenced-code-blocks'])
    template['creation_date'] = request.json['data']['creation_date']
    page['code_snippets'].update({template['id']: template})
    print(f"Received new code snippet for {page['title']}")
    save_data(content_dict)
    return Response("Okay", status=200, mimetype='application/json')


@app.route("/snippets", methods=['PUT'])
def update_snippet():
    global content_dict
    page_id = request.json['data']['pageID']
    page = find_page(page_id)
    snippet = page['code_snippets'].get(request.json['data']['snippetID'])
    snippet['title'] = request.json['data']['title']
    snippet['description'] = request.json['data']['description']
    snippet['language'] = request.json['data']['language']
    snippet['raw'] = request.json['data']['code']
    snippet['marked'] = markdown2.markdown(f"\n```{snippet['language']}\n{snippet['raw']}\n```",
                                           extras=['fenced-code-blocks'])
    print(f"Received update for code snippet {snippet['title']} from {page['title']}")
    save_data(content_dict)
    return Response("Okay", status=200, mimetype='application/json')


def save_data(data):
    with open(cnst.data_path + cnst.v1_name, 'wb') as f:
        pickle.dump(data, f)


def read_data():
    if not (os.path.exists(cnst.data_path + cnst.v1_name)):
        return {}
    with open(cnst.data_path + cnst.v1_name, 'rb') as f:
        loaded_data = pickle.load(f)
    return dict(loaded_data)


def find_page(id, project_id=None):
    global content_dict
    if project_id is not None:
        project = content_dict.get(project_id)
        for pageID in project['pages'].keys():
            if pageID == id:
                return project['pages'].get(pageID)
    else:
        for project_ID in content_dict.keys():
            project = content_dict.get(project_ID)
            for pageID in project['pages'].keys():
                if pageID == id:
                    return project['pages'].get(pageID)


def main():
    app.run(host='0.0.0.0', port=3001)


if __name__ == "__main__":
    content_dict = read_data()
    ## make backup
    ## content integrity
    ## remove unlinked content
    ## verify links

    main()
