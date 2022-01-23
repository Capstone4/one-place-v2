from flask import Flask, request, Response, send_file
from flask_cors import CORS
import markdown2
import time
import json
import hashlib
import pickle
import os
import zipfile
import socket
import re
import copy
import constants as cnst

app = Flask(__name__)
CORS(app)
content_dict = None
last_save = time.time()


@app.route("/save", methods=["GET"])
def remote_save():
    global content_dict
    save_data(content_dict)
    return Response("ok", status=200, mimetype='application/json')


@app.route("/backup", methods=["GET"])
def remote_backup():
    remove_unlinked_files(content_dict)
    remove_unlinked_images(content_dict)
    backup()
    print("received backup command")
    return Response("ok", status=200, mimetype='application/json')


@app.route("/render", methods=["GET"])
def update_render():
    global content_dict
    page_id = request.args.get('pageID')
    page = find_page(page_id)
    page['last_render'] = request.args.get('time')
    save_data(content_dict)
    print(f"Updated render time for {page['title']}")
    return Response("ok", status=200, mimetype='application/json')


@app.route("/projects", methods=["GET"])
def get_projects():
    return_json = {"projects": [content_dict.get(key) for key in content_dict.keys()]}
    return Response(json.dumps(return_json), status=200, mimetype='application/json')


@app.route("/projects", methods=["POST"])
def create_project():
    global content_dict
    template = copy.deepcopy(cnst.project_dict)
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
    # TODO FINISH UPDATE
    global content_dict
    project_id = request.args.get('id')
    project = content_dict.get(project_id)
    project['title'] = request.args.get('title')
    save_data(content_dict)
    return Response(json.dumps({'status': 'ok'}), status=200, mimetype='application/json')


@app.route("/delete", methods=["GET"])
def delete_project():
    global content_dict
    backup()
    id_to_remove = request.args.get('id')
    if id_to_remove in content_dict.keys():
        content_dict.pop(id_to_remove)
    else:
        for key in content_dict.keys():
            project = content_dict.get(key)
            if id_to_remove in project['files'].keys():
                print(f"deleted {id_to_remove}")
                project['files'].pop(id_to_remove)
            if id_to_remove in project['pages'].keys():
                print(f"deleted {id_to_remove}")
                project['pages'].pop(id_to_remove)
            for page_id in project['pages'].keys():
                page = project['pages'].get(page_id)
                if id_to_remove in page['code_snippets'].keys():
                    print(f"deleted {id_to_remove}")
                    page['code_snippets'].pop(id_to_remove)
    save_data(content_dict)
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
        print(f'Message update for {page["title"]}')
        save_data_from_update(content_dict)
    return Response("Ok", status=200, mimetype='application/json')


@app.route("/pages", methods=["POST"])
def create_page():
    global content_dict
    template = copy.deepcopy(cnst.page_dict)
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


@app.route("/files", methods=["POST"])
def save_file():
    global content_dict
    file = request.files['file']
    prehash = str(time.time()) + file.filename
    extension = file.filename[-4:]
    id = hashlib.sha256(bytes(prehash, 'utf-8')).hexdigest()
    file_name = id + extension
    file.save(os.path.join(cnst.files, file_name))
    project = content_dict.get(request.form['project_id'])
    template = copy.deepcopy(cnst.files_dict)
    template['title'] = request.form['title']
    template['description'] = request.form['description']
    template['upload_date'] = int(request.form['upload_date'])
    template['id'] = id
    template['file_name'] = file_name
    template['original_file_name'] = file.filename
    project['files'].update({template['id']: template})
    save_data(content_dict)
    print(f"received {template['original_file_name']} for {project['title']}")
    return Response(json.dumps({'file': file_name}), status=200, mimetype='application/json')


@app.route("/files", methods=["GET"])
def get_file():
    print(request.args.get('project_id'))
    print(request.args.get('file_id'))
    project = content_dict.get(request.args.get('project_id'))
    file = project['files'].get(request.args.get('file_id'))
    return send_file(cnst.files + file['file_name'], download_name=file['original_file_name'])


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
    template = copy.deepcopy(cnst.code_snippets_dict)
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
    global last_save
    last_save = time.time()
    with open(cnst.data_path + cnst.v1_name, 'wb') as f:
        pickle.dump(data, f)
    print("saved content")


def save_data_from_update(data):
    global last_save
    if (time.time() - last_save) > (10 * 60):
        last_save = time.time()
        save_data(data)


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


def backup():
    source_dir = cnst.data_path
    image_dir = cnst.images
    files_dir = cnst.files
    save_dir = cnst.backups
    images = [f for f in os.listdir(image_dir) if os.path.isfile(os.path.join(image_dir, f))]
    files = [f for f in os.listdir(files_dir) if os.path.isfile(os.path.join(files_dir, f))]
    root = [f for f in os.listdir(source_dir) if os.path.isfile(os.path.join(source_dir, f))]
    with zipfile.ZipFile(f"{save_dir}{time.time()}.zip", 'w') as zipf:
        [zipf.write(image_dir + f, '/images/' + f) for f in images]
        [zipf.write(files_dir + f, '/files/' + f) for f in files]
        [zipf.write(source_dir + f, '/' + f) for f in root]


def verify_keys(dictionary):
    for project_id in dictionary.keys():
        # verify project keys
        project = dictionary.get(project_id)
        project = verify_project(project)
        for page_id in project['pages'].keys():
            page = project['pages'].get(page_id)
            page = verify_page(page)
        for file_id in project['files'].keys():
            file = project['files'].get(file_id)
            file = verify_file_dict(file)
    return dictionary


def verify_project(project):
    temp = copy.deepcopy(cnst.project_dict)
    for project_key in temp.keys():
        if not (project_key in project.keys()):
            # set default values
            project[project_key] = temp[project_key]
    return project


def verify_page(page):
    temp = copy.deepcopy(cnst.page_dict)
    for page_key in temp.keys():
        if not (page_key in page.keys()):
            # set default values
            page[page_key] = temp[page_key]
    # if len(page['code_snippets'].keys()) == 0:
    #     page['code_snippets'] = dict()
    for code_snippet_id in page['code_snippets'].keys():
        snippet = page['code_snippets'].get(code_snippet_id)
        snippet = verify_snippet(snippet)
    # if len(page['pages'].keys()) == 0:
    #     page['pages'] = dict()
    for sub_page_id in page['pages'].keys():
        sub_page = page['pages'].get(sub_page_id)
        sub_page = verify_page(sub_page)

    return page


def verify_snippet(snippet):
    temp = copy.deepcopy(cnst.code_snippets_dict)

    for snippet_key in temp.keys():
        if not (snippet_key in snippet.keys()):
            # set default values
            snippet[snippet_key] = temp[snippet_key]
    return snippet


def verify_file_dict(file_dict):
    temp = copy.deepcopy(cnst.files_dict)
    for file_key in temp.keys():
        if not (file_key in file_dict.keys()):
            # set default values
            file_dict[file_key] = temp[file_key]
    return file_dict


def remove_unlinked_files(content):
    linked_file_names = set()
    for project_id in content.keys():
        project = content.get(project_id)
        for file_id in project['files'].keys():
            file = project['files'].get(file_id)
            linked_file_names.add(file['file_name'])

    files = [f for f in os.listdir(cnst.files) if os.path.isfile(os.path.join(cnst.files, f))]
    for file in files:
        if not (file in linked_file_names):
            print(f"removing {file}")
            os.remove(cnst.files + file)


def remove_unlinked_images(content):
    content_string = ""
    for project_id in content.keys():
        project = content.get(project_id)
        for page_id in project['pages'].keys():
            page = project['pages'].get(page_id)
            content_string += page['content'] if page['content'] is not None else ""

    images = [f for f in os.listdir(cnst.images) if os.path.isfile(os.path.join(cnst.images, f))]
    for image in images:
        if content_string.find(image[:-4]) == -1:
            print(f"removing image {image}")
            os.remove(cnst.images + image)


def update_image_links(content):
    for project_id in content.keys():
        project = content.get(project_id)
        for page_id in project['pages']:
            page = project['pages'].get(page_id)
            if page['content'] is None:
                continue
            if page['content'].find(get_ip()) == -1:
                page['content'] = fix_links(page['content'])


def fix_links(content):
    current_ip = get_ip()
    pattern = r"!\[image\]\(http://[\S]*:3001"
    replacement = f"![image](http://{current_ip}:3001"
    return re.sub(pattern, replacement, content)


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def create_review_list(content):
    with open(cnst.review_list, "w") as f:
        for project_id in content.keys():
            project = content.get(project_id)
            f.write(f"{project['title']}\n")
            for page_id in project['pages'].keys():
                page = project['pages'].get(page_id)
                if (page['content'] is None) or (float(page['last_render']) < 10):
                    continue
                else:
                    f.write(f"{page['title']}: {(time.time() - float(page['last_render']) / 1000) / 86400:.2f} days \n")
            f.write(f"\n")


def main():
    app.run(host='0.0.0.0', port=3001)


if __name__ == "__main__":
    backup()
    content_dict = read_data()
    content_dict = verify_keys(content_dict)
    remove_unlinked_files(content_dict)
    remove_unlinked_images(content_dict)
    update_image_links(content_dict)
    create_review_list(content_dict)
    main()
