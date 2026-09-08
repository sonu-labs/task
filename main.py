import os, json, uuid, base64
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

DATA_FILE = "tasks_data.json"

CATEGORIES = ["Design","Coding","Writing","Marketing","Video","Data Entry","Research","Testing","AI Training","Translation","Other"]

# Initial mock data
MOCK_TASKS = [
    {
        "id": "t1",
        "title": "Logo Design for Startup - Minimal Tech Logo",
        "description": "Ek modern tech startup ke liye minimal logo chahiye. 2-3 concepts dena hai, source file + PNG chahiye. Brand name: NexaAI, colors blue/black.",
        "category": "Design",
        "reward": 500,
        "deadline": (datetime.now()+timedelta(days=3)).isoformat(),
        "guide": ["Client brief padho: NexaAI tech/AI brand hai", "Dribbble/Behance se 5 reference logo dekho", "2-3 concept Figma/Illustrator me banao", "PNG + JPG + AI source export karo", "Screenshot ke saath submit karo"],
        "tags": ["logo","figma","branding"],
        "status": "open",
        "postedBy": {"id":"u2","name":"Rahul Sharma","avatar":"RS"},
        "claimedBy": None,
        "proof": None,
        "createdAt": (datetime.now()-timedelta(hours=5)).isoformat(),
        "difficulty": "Medium"
    },
    {
        "id": "t2",
        "title": "Python Script - Excel to JSON Converter",
        "description": "Excel file ko JSON me convert karne ka Python script chahiye. Pandas use karo, error handling bhi ho. GitHub repo bana ke do.",
        "category": "Coding",
        "reward": 800,
        "deadline": (datetime.now()+timedelta(days=2)).isoformat(),
        "guide": ["Sample Excel file download karo", "Pandas se read_excel karo", "JSON conversion logic likho", "Error handling + CLI args add karo", "GitHub pe push karke screenshot lo"],
        "tags": ["python","pandas","automation"],
        "status": "open",
        "postedBy": {"id":"u3","name":"Aman Dev","avatar":"AD"},
        "claimedBy": None,
        "proof": None,
        "createdAt": (datetime.now()-timedelta(hours=2)).isoformat(),
        "difficulty": "Hard"
    },
    {
        "id": "t3",
        "title": "Instagram Reels - 3 Viral Hooks Writing",
        "description": "Fashion niche ke liye 3 Instagram reels ke liye hook + caption + hashtags chahiye. Hinglish me, Gen-Z tone.",
        "category": "Writing",
        "reward": 250,
        "deadline": (datetime.now()+timedelta(days=1)).isoformat(),
        "guide": ["Fashion trends research karo (Myntra, Instagram)", "3 alag hook lines likho - 0-3 sec grabber", "Caption 50-80 words Hinglish me", "30 hashtags mix (niche + broad)", "Doc bana ke screenshot submit karo"],
        "tags": ["content","instagram","hinglish"],
        "status": "claimed",
        "postedBy": {"id":"u4","name":"Sneha K","avatar":"SK"},
        "claimedBy": {"id":"u5","name":"Priya Writes","avatar":"PW"},
        "proof": None,
        "createdAt": (datetime.now()-timedelta(hours=8)).isoformat(),
        "difficulty": "Easy"
    },
    {
        "id": "t4",
        "title": "Test Mobile App & Report Bugs (Android)",
        "description": "Hamari nayi delivery app ko test karna hai. 10 test cases diye jayenge, bug video + screenshot chahiye.",
        "category": "Testing",
        "reward": 400,
        "deadline": (datetime.now()+timedelta(days=4)).isoformat(),
        "guide": ["APK download karo (link guide me hai)", "10 test cases follow karo (login, order, payment)", "Har bug ka screenshot + screen recording lo", "Google Sheet me bug report bharo", "Sheet link + screenshots submit karo"],
        "tags": ["qa","android","testing"],
        "status": "submitted",
        "postedBy": {"id":"u6","name":"TechKart","avatar":"TK"},
        "claimedBy": {"id":"u7","name":"Vikas Tester","avatar":"VT"},
        "proof": {"screenshot":"https://via.placeholder.com/600x400/0ea5e9/ffffff?text=Bug+Report+Sheet","note":"Saare 10 cases test kiye, 3 bugs mile. Sheet ready hai.","submittedAt": datetime.now().isoformat()},
        "createdAt": (datetime.now()-timedelta(days=1)).isoformat(),
        "difficulty": "Medium"
    },
    {
        "id": "t5",
        "title": "YouTube Thumbnail Design - Finance Video",
        "description": "Finance youtube video ke liye high CTR thumbnail chahiye. Title: '₹500 se ₹5 Lakh kaise banaye?' Bold text, face, money elements.",
        "category": "Design",
        "reward": 300,
        "deadline": (datetime.now()+timedelta(days=1)).isoformat(),
        "guide": ["Reference thumbnails dekho (finance niche top videos)", "Canva/Photoshop me 1280x720 banao", "Face + bold hindi/english text use karo", "CTR elements: arrow, money, shocked expression", "JPG export + source submit karo"],
        "tags": ["thumbnail","youtube","canva"],
        "status": "completed",
        "postedBy": {"id":"u8","name":"Finance Gyaan","avatar":"FG"},
        "claimedBy": {"id":"u1","name":"Aap (Demo User)","avatar":"AU"},
        "proof": {"screenshot":"https://via.placeholder.com/600x400/22c55e/ffffff?text=Thumbnail+Done","note":"Thumbnail ready, 2 variations banaye!","submittedAt": (datetime.now()-timedelta(hours=1)).isoformat()},
        "createdAt": (datetime.now()-timedelta(days=2)).isoformat(),
        "difficulty": "Easy"
    },
    {
        "id": "t6",
        "title": "Data Entry - 100 Business Leads",
        "description": "Google se 100 startup founders ke leads nikalne hain: Name, Company, Email, LinkedIn. Excel me dena hai.",
        "category": "Data Entry",
        "reward": 600,
        "deadline": (datetime.now()+timedelta(days=5)).isoformat(),
        "guide": ["Google + LinkedIn se search karo: 'startup founder India'", "Hunter.io ya Apollo se email find karo", "Excel me 4 columns banao", "100 unique leads bharo (no duplicate)", "Excel screenshot + file submit karo"],
        "tags": ["leads","excel","research"],
        "status": "open",
        "postedBy": {"id":"u9","name":"LeadGen Pro","avatar":"LG"},
        "claimedBy": None,
        "proof": None,
        "createdAt": (datetime.now()-timedelta(hours=12)).isoformat(),
        "difficulty": "Medium"
    },
    {
        "id": "t7",
        "title": "AI Training - 50 Images Labeling",
        "description": "50 images me car, bike, person ko label karna hai LabelImg tool se. YOLO format me chahiye.",
        "category": "AI Training",
        "reward": 450,
        "deadline": (datetime.now()+timedelta(days=3)).isoformat(),
        "guide": ["Dataset download karo (Drive link)", "LabelImg install karo", "Har image me bounding box draw karo", "Classes: car, bike, person", "YOLO txt files + screenshot submit karo"],
        "tags": ["labeling","yolo","ai"],
        "status": "open",
        "postedBy": {"id":"u10","name":"AI Labs","avatar":"AI"},
        "claimedBy": None,
        "proof": None,
        "createdAt": (datetime.now()-timedelta(hours=6)).isoformat(),
        "difficulty": "Easy"
    },
    {
        "id": "t8",
        "title": "Translate 2000 Words EN -> Hindi",
        "description": "E-commerce app ke 2000 words English se Hindi me translate karne hain. Natural Hindi, Google translate copy-paste nahi chalega.",
        "category": "Translation",
        "reward": 350,
        "deadline": (datetime.now()+timedelta(days=2)).isoformat(),
        "guide": ["Excel sheet download karo (English strings)", "Natural Hindi me translate karo (Hinglish allowed)", "Context ka dhyan rakho (app UI strings)", "Proofread karo", "Sheet ka screenshot submit karo"],
        "tags": ["hindi","translation","app"],
        "status": "open",
        "postedBy": {"id":"u11","name":"ShopEasy","avatar":"SE"},
        "claimedBy": None,
        "proof": None,
        "createdAt": (datetime.now()-timedelta(hours=3)).isoformat(),
        "difficulty": "Easy"
    },
]

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE,'r',encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"tasks": MOCK_TASKS, "users": []}

def save_data(data):
    with open(DATA_FILE,'w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

data_store = load_data()

@app.route('/')
def index():
    return send_from_directory('static','index.html')

@app.route('/api/stats')
def stats():
    tasks = data_store["tasks"]
    return jsonify({
        "total": len(tasks),
        "open": len([t for t in tasks if t["status"]=="open"]),
        "claimed": len([t for t in tasks if t["status"]=="claimed"]),
        "submitted": len([t for t in tasks if t["status"]=="submitted"]),
        "completed": len([t for t in tasks if t["status"]=="completed"]),
        "totalReward": sum(t["reward"] for t in tasks if t["status"]=="completed"),
        "categories": CATEGORIES
    })

@app.route('/api/tasks', methods=['GET','POST'])
def tasks():
    if request.method == 'GET':
        q = request.args.get('search','').lower()
        cat = request.args.get('category','All')
        status = request.args.get('status','All')
        result = data_store["tasks"]
        if cat != "All":
            result = [t for t in result if t["category"]==cat]
        if status != "All":
            # map UI status
            status_map = {"Open":"open","In Progress":"claimed","Review":"submitted","Completed":"completed"}
            s = status_map.get(status, status.lower())
            result = [t for t in result if t["status"]==s]
        if q:
            result = [t for t in result if q in t["title"].lower() or q in t["description"].lower() or q in " ".join(t["tags"]).lower()]
        # sort newest first
        result = sorted(result, key=lambda x: x["createdAt"], reverse=True)
        return jsonify(result)
    else:
        d = request.json
        new_task = {
            "id": "t"+uuid.uuid4().hex[:6],
            "title": d.get("title","Untitled Task"),
            "description": d.get("description",""),
            "category": d.get("category","Other"),
            "reward": int(d.get("reward",100)),
            "deadline": d.get("deadline", (datetime.now()+timedelta(days=3)).isoformat()),
            "guide": d.get("guide", []),
            "tags": d.get("tags", []),
            "status": "open",
            "postedBy": d.get("postedBy", {"id":"u1","name":"Aap","avatar":"AU"}),
            "claimedBy": None,
            "proof": None,
            "createdAt": datetime.now().isoformat(),
            "difficulty": d.get("difficulty","Medium")
        }
        data_store["tasks"].insert(0,new_task)
        save_data(data_store)
        return jsonify(new_task), 201

@app.route('/api/tasks/<tid>', methods=['GET','DELETE'])
def task_detail(tid):
    task = next((t for t in data_store["tasks"] if t["id"]==tid), None)
    if not task:
        return jsonify({"error":"Not found"}),404
    if request.method=='GET':
        return jsonify(task)
    else:
        data_store["tasks"] = [t for t in data_store["tasks"] if t["id"]!=tid]
        save_data(data_store)
        return jsonify({"ok":True})

@app.route('/api/tasks/<tid>/claim', methods=['POST'])
def claim_task(tid):
    task = next((t for t in data_store["tasks"] if t["id"]==tid), None)
    if not task: return jsonify({"error":"Not found"}),404
    if task["status"]!="open":
        return jsonify({"error":"Task already claimed or completed"}),400
    d = request.json
    # prevent self-claim
    if d.get("userId")==task["postedBy"]["id"]:
        return jsonify({"error":"Apna hi task claim nahi kar sakte!"}),400
    task["status"]="claimed"
    task["claimedBy"]= {"id": d.get("userId","u1"), "name": d.get("userName","Worker"), "avatar": d.get("userName","W")[:2].upper()}
    save_data(data_store)
    return jsonify(task)

@app.route('/api/tasks/<tid>/submit', methods=['POST'])
def submit_task(tid):
    task = next((t for t in data_store["tasks"] if t["id"]==tid), None)
    if not task: return jsonify({"error":"Not found"}),404
    if task["status"]!="claimed":
        return jsonify({"error":"Task not in claimed state"}),400
    d = request.json
    # optional permission check claimedBy
    # if d.get("userId") != task["claimedBy"]["id"]: return error...
    task["status"]="submitted"
    task["proof"]={
        "screenshot": d.get("screenshot",""),
        "note": d.get("note",""),
        "submittedAt": datetime.now().isoformat()
    }
    save_data(data_store)
    return jsonify(task)

@app.route('/api/tasks/<tid>/verify', methods=['POST'])
def verify_task(tid):
    task = next((t for t in data_store["tasks"] if t["id"]==tid), None)
    if not task: return jsonify({"error":"Not found"}),404
    d = request.json
    action = d.get("action")
    if action=="approve":
        task["status"]="completed"
    elif action=="reject":
        task["status"]="claimed"
        task["proof"]=None
    elif action=="cancel":
        task["status"]="open"
        task["claimedBy"]=None
        task["proof"]=None
    save_data(data_store)
    return jsonify(task)

@app.route('/api/tasks/<tid>/abandon', methods=['POST'])
def abandon(tid):
    task = next((t for t in data_store["tasks"] if t["id"]==tid), None)
    if not task: return jsonify({"error":"Not found"}),404
    task["status"]="open"
    task["claimedBy"]=None
    task["proof"]=None
    save_data(data_store)
    return jsonify(task)

@app.route('/api/leaderboard')
def leaderboard():
    # mock leaderboard based on completed tasks
    lb = [
        {"rank":1,"name":"Rohan Dev","avatar":"RD","completed":42,"earned":12400},
        {"rank":2,"name":"Aap (Demo)","avatar":"AU","completed":18,"earned":5600},
        {"rank":3,"name":"Priya Writes","avatar":"PW","completed":15,"earned":4800},
        {"rank":4,"name":"Vikas Tester","avatar":"VT","completed":12,"earned":3600},
        {"rank":5,"name":"Sneha K","avatar":"SK","completed":9,"earned":2700},
    ]
    return jsonify(lb)

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join('static', path)):
        return send_from_directory('static', path)
    return send_from_directory('static','index.html')

if __name__=='__main__':
    os.makedirs('static', exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    print(f"TaskHub running on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
