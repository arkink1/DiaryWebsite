import os
from werkzeug.security import check_password_hash, generate_password_hash
from flask import Flask, flash, session, render_template, request, redirect, url_for
from flask_session import Session
from flask_socketio import SocketIO, emit
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import scoped_session, sessionmaker
import requests
from datetime import datetime

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))
socketio = SocketIO(app)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

@app.route("/")
def index():
    if session.get("loggedIn"):
        return redirect("/explore")
    else:
        return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("loggedIn"):
        return redirect("/write")
    else:
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            info = db.execute("SELECT username, password FROM users WHERE username = :username", {"username": username}).fetchone();
            try:
                if info[0] == None or check_password_hash(info[1], password) == False:
                    return render_template("login.html", message="Error: Username and/or password invalid.")
                else:
                    session["username"] = username
                    session["loggedIn"] = True
                    return redirect("/explore")
            except TypeError:
                    return render_template("login.html", message="Error: Username and/or password invalid.")

        else:
            return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("loggedIn"):
        return redirect("/write")
    else:
        if request.method == "POST":
            email = request.form.get('email')
            username = request.form.get('username')
            password1 = request.form.get('password')
            password2 = request.form.get('password2')
            test = email.split('@')
            if len(test) != 2 or test[1] == '':
                return render_template("register.html", message="Invalid email format", info=['email', username])
            atPart = test[1]
            dotPart = atPart.split('.')
            if len(dotPart) == 1:
                return render_template("register.html", message="Invalid email format", info=['email', username])
            for i in dotPart:
                if i == '':
                    return render_template("register.html", message="Invalid email format", info=['email', username])
            if (db.execute("SELECT * FROM users WHERE email= :email", {"email":email}).rowcount > 0):
                return render_template("register.html", message="Email already in use", info=['email', username])
            elif (db.execute("SELECT * FROM users WHERE username= :username", {"username":username}).rowcount > 0):
                return render_template("register.html", message="Username already in use", info=['username', email])
            elif password1 != password2:
                return render_template("register.html", message="Passwords don't match", info=['passwords', email, username])
            else:
                os.mkdir(os.path.join(APP_ROOT, 'static/', username))
                hashedPassword = generate_password_hash(password1, method="pbkdf2:sha256", salt_length=7)
                db.execute("INSERT into users (email, username, password) VALUES (:email, :username, :password)", {"email":email, "username":username, "password":hashedPassword})
                db.commit()
                session["username"] = username
                session["loggedIn"] = True
                return redirect("/explore")
        else:
            return render_template("register.html", info=['None'])

@app.route("/logout")
def logout():
    session["username"] = None
    session["loggedIn"] = False
    session["place"] = None
    session.clear()
    return redirect("/")

@app.route("/write", methods=["POST", "GET"])
def write():
    if session.get("loggedIn"):
        session["place"] = 'write'
        if request.method == "POST":
            if request.form.get("submitBtn") == 'write':
                author = session.get("username")
                content = request.form.get("content")
                date = datetime.now().strftime("%d-%m-%Y")
                privacy = request.form.get("privacy")
                title = request.form.get("title").title()
                photos = request.files.getlist("file")
                target = os.path.join(APP_ROOT, 'static/', author, date)
                photoList = []
                if not os.path.isdir(target):
                    os.mkdir(target)
                if photos[0].filename != '':
                    photoList = []
                    for photo in photos:
                        picName = photo.filename
                        l = list(picName)
                        for i in l:
                            if i == ',':
                                l.remove(i)
                        filename = "".join(l)
                        location = "/".join([target, filename])
                        photo.save(location)
                        photoList.append(filename)
                    finalPhotoList = ','.join(photoList)
                    db.execute("INSERT into posts (content, publishdate, privacy, photopath, author, title) VALUES (:content, :date, :privacy, :filename, :author, :title)", {"content":content, "date":date, "privacy":privacy, "filename":finalPhotoList, "author":author, "title":title})
                    db.commit()
                    return redirect("/diary/" + session.get("username"))
                else:
                    db.execute("INSERT into posts (content, publishdate, privacy, author, title) VALUES (:content, :date, :privacy, :author, :title)", {"content":content, "date":date, "privacy":privacy, "author":author, "title":title})
                    db.commit()
                    return redirect("/diary/" + session.get("username"))
            else:
                postId = request.form.get('submitBtn')
                author = session.get("username")
                content = request.form.get("content")
                date = datetime.now().strftime("%d-%m-%Y")
                privacy = request.form.get("privacy")
                title = request.form.get("title").title()
                photos = request.files.getlist("file")
                target = os.path.join(APP_ROOT, 'static/', author, date)
                if photos[0].filename != '':
                    photoList = []
                    for photo in photos:
                        picName = photo.filename
                        l = list(picName)
                        for i in l:
                            if i == ',':
                                l.remove(i)
                        filename = "".join(l)
                        location = "/".join([target, filename])
                        photo.save(location)
                        photoList.append(filename)
                    finalPhotoList = ','.join(photoList)
                    db.execute("UPDATE posts SET content= :content, privacy= :privacy, title= :title, photopath= :photopath WHERE id= :id", {"content":content, "privacy":privacy, "title":title, "id":postId, "photopath":finalPhotoList})
                    db.commit()
                    return redirect("/diary/" + session.get("username"))
                else:
                    db.execute("UPDATE posts SET content= :content, privacy= :privacy, title= :title WHERE id= :id", {"content":content, "privacy":privacy, "title":title, "id":postId})
                    db.commit()
                    return redirect("/diary/" + session.get("username"))
        else:
            author = session.get("username")
            lastPost = db.execute("SELECT publishdate FROM posts WHERE author= :author ORDER by id DESC LIMIT 1", {"author":author}).fetchone()
            if lastPost:
                date = datetime.now().strftime("%d-%m-%Y")
                if lastPost[0] == date:
                    info = db.execute("SELECT content, privacy, title, photopath, id FROM posts WHERE author= :author AND publishdate= :date", {"author":author, "date":date}).fetchone()
                    cleanedInfo = []
                    cleanedInfo.append(info[0])
                    cleanedInfo.append(info[1])
                    cleanedInfo.append(info[2])
                    imgs = info[3]
                    if imgs != None:
                        imgs = info[3].split(',')
                        cleanedInfo.append(imgs)
                        numOfImgs = len(cleanedInfo[3])
                        cleanedInfo.append(numOfImgs)
                    else:
                        cleanedInfo.append('')
                        cleanedInfo.append(0)
                    cleanedInfo.append(info[4])
                    return render_template("write.html", info=cleanedInfo, content=True, message="You have already started a diary entry for today")
                else:
                    return render_template("write.html")
            else:
                return render_template("write.html")
            return render_template("write.html")
    else:
        return redirect("/")

@app.route("/settings", methods=["POST", "GET"])
def settings():
    if session.get("loggedIn"):
        session["place"] = 'settings'
        if request.method == "POST":
            if request.form.get("submitBtn") == "username":
                newUsername = request.form.get("username")
                currentUsername = session.get("username")
                if session.get("username") == newUsername:
                    return render_template("settings.html", message="Enter a different username")
                elif db.execute("SELECT * FROM users WHERE username= :username", {"username":newUsername}).rowcount > 0:
                    return render_template("settings.html", message="This username is already in use")
                else:
                    db.execute("UPDATE users SET username= :newUsername WHERE username= :currentUsername", {"newUsername":newUsername, "currentUsername":currentUsername})
                    db.commit()
                    session["username"] = newUsername
                    posts = db.execute("SELECT id FROM posts WHERE author= :username", {"username":currentUsername}).fetchall()
                    for post in posts:
                        db.execute("UPDATE posts SET author= :newUsername WHERE id= :id", {"newUsername":newUsername, "id":post[0]})
                    db.commit()
                    old = os.path.join(APP_ROOT, 'static/', currentUsername)
                    new = os.path.join(APP_ROOT, 'static/', newUsername)
                    os.rename(old, new)
                    return render_template("settings.html", message="Successfully updated username")
            else:
                username = session.get("username")
                currentPassword = request.form.get("oldPass")
                info = db.execute("SELECT username, password FROM users WHERE username = :username", {"username": username}).fetchone();
                if check_password_hash(info[1], currentPassword) == False:
                    return render_template("settings.html", message="Error: Invalid password.")
                else:
                    if request.form.get("newPass1") == request.form.get("newPass2"):
                        password = request.form.get("newPass1")
                        hashedPassword = generate_password_hash(password, method="pbkdf2:sha256", salt_length=7)
                        db.execute("UPDATE users SET password= :password WHERE username= :username", {"username":username, "password":hashedPassword})
                        db.commit()
                        return render_template("settings.html", message="Password successfully changed")
                    else:
                        return render_template("settings.html", message="Error: Passwords don't match")
        else:
            return render_template("settings.html")
    else:
        return redirect("/")

@app.route("/explore", methods=["POST", "GET"])
def explore():
    if session.get("loggedIn"):
        session['explore'] = None
        session["place"] = 'explore'
        if request.method == "POST":
            username = request.form.get('userSearch')
            user = "%" + username + "%"
            session['explore'] = user
            posts = db.execute("SELECT * FROM posts WHERE privacy='public' AND (author LIKE :author OR publishdate LIKE :date) ORDER by id DESC LIMIT 5", {"author":user, "date":user}).fetchall()
            postCount = db.execute("SELECT COUNT(*) FROM posts WHERE privacy='public' AND (author LIKE :author OR publishdate LIKE :date)", {"author":user, "date":user}).fetchone()[0]
            cleanedPosts = []
            postIds = []
            for post in posts:
                postIds.append(post[0])
            postIds.sort()
            for post in posts:
                onePost = []
                onePost.append(post[0])
                onePost.append(post[1])
                onePost.append(post[2])
                onePost.append(post[3])
                if post[4] != None:
                    imgList = post[4].split(',')
                    onePost.append(imgList)
                else:
                    onePost.append('')
                onePost.append(post[5])
                onePost.append(post[6])
                cleanedPosts.append(onePost)
            if len(postIds) > 0:
                postIds.sort()
                postId = postIds[0]
                return render_template("explore.html", posts=cleanedPosts, search=username, postId=postId, postCount=postCount)
            else:
                return render_template("explore.html", posts=cleanedPosts, search=username, postCount=postCount)
        else:
            posts = db.execute("SELECT * FROM posts WHERE (privacy='public') ORDER by id DESC LIMIT 5").fetchall()
            postCount = db.execute("SELECT COUNT(*) FROM posts WHERE privacy='public'").fetchone()[0]
            postIds = []
            for post in posts:
                postIds.append(post[0])
            postIds.sort()
            cleanedPosts = []
            for post in posts:
                onePost = []
                onePost.append(post[0])
                onePost.append(post[1])
                onePost.append(post[2])
                onePost.append(post[3])
                if post[4] != None:
                    imgList = post[4].split(',')
                    onePost.append(imgList)
                else:
                    onePost.append('')
                onePost.append(post[5])
                onePost.append(post[6])
                cleanedPosts.append(onePost)
            if len(postIds) > 0:
                postId = postIds[0]
                return render_template("explore.html", posts=cleanedPosts, postId=postId, postCount=postCount)
            else:
                return render_template("explore.html", posts=cleanedPosts, postCount=postCount)
    else:
        return redirect("/")

@socketio.on('getMorePosts')
def getMorePosts(data):
    if session.get('explore') == None:
        lastPostId = data['lastPostId']
        morePosts = db.execute("SELECT * FROM posts WHERE id < :lastPostId AND privacy='public' ORDER by id DESC LIMIT 5", {"lastPostId":lastPostId}).fetchall()
        postCount = db.execute("SELECT COUNT(*) FROM posts WHERE id < :lastPostId AND privacy='public'", {"lastPostId":lastPostId}).fetchone()[0]
        cleanedPosts = []
        postIds = []
        for post in morePosts:
            postIds.append(post[0])
            onePost = []
            onePost.append(post[0])
            onePost.append(post[1])
            onePost.append(post[2])
            onePost.append(post[3])
            if post[4] != None:
                imgList = post[4].split(',')
                onePost.append(imgList)
            else:
                onePost.append('')
            onePost.append(post[5])
            onePost.append(post[6])
            cleanedPosts.append(onePost)
        lenCleanedPosts = len(cleanedPosts)
        postIds.sort()
        lastPost = postIds[0]
        emit('newPosts', {'posts':cleanedPosts, 'currentUser':session.get('username'), 'lenCleanedPosts':lenCleanedPosts, "numOfPostsLeft":postCount, "lastPostId":lastPost})
    else:
        lastPostId = data['lastPostId']
        search = session.get('explore')
        morePosts = db.execute("SELECT * FROM posts WHERE id < :lastPostId AND privacy='public' AND (author LIKE :search OR publishdate LIKE :search) ORDER by id DESC LIMIT 5", {"lastPostId":lastPostId, "search":search}).fetchall()
        postCount = db.execute("SELECT COUNT(*) FROM posts WHERE id < :lastPostId AND privacy='public' AND (author LIKE :search OR publishdate LIKE :search)", {"lastPostId":lastPostId, "search":search}).fetchone()[0]
        cleanedPosts = []
        postIds = []
        for post in morePosts:
            postIds.append(post[0])
            onePost = []
            onePost.append(post[0])
            onePost.append(post[1])
            onePost.append(post[2])
            onePost.append(post[3])
            if post[4] != None:
                imgList = post[4].split(',')
                onePost.append(imgList)
            else:
                onePost.append('')
            onePost.append(post[5])
            onePost.append(post[6])
            cleanedPosts.append(onePost)
        lenCleanedPosts = len(cleanedPosts)
        postIds.sort()
        if len(postIds) > 0:
            lastPost = postIds[0]
            emit('newPosts', {'posts':cleanedPosts, 'currentUser':session.get('username'), 'lenCleanedPosts':lenCleanedPosts, "numOfPostsLeft":postCount, "lastPostId":lastPost})
        else:
            emit('newPosts', {'posts':cleanedPosts, 'currentUser':session.get('username'), 'lenCleanedPosts':lenCleanedPosts, "numOfPostsLeft":postCount})

@socketio.on('showedNewPost')
def beReady():
    emit('newSeeMore')

@app.route("/diary/<string:username>", methods=["GET", "POST"])
def diary(username):
    if session.get("loggedIn"):
        session["place"] = 'diary'
        session['diary'] = None
        if request.method == "POST":
            username = request.form.get("searchBtn")
            find = request.form.get("titleSearch").title()
            search = "%" + find + "%"
            if username == session.get("username"):
                session['diary'] = [session.get('username'), search]
                results = db.execute("SELECT * FROM posts WHERE author= :username AND (title LIKE :search OR publishdate LIKE :search) ORDER by id DESC LIMIT 5", {"username":username, "search":search}).fetchall()
                numOfResults = db.execute("SELECT COUNT(*) FROM posts WHERE author= :username AND (title LIKE :search OR publishdate LIKE :search)", {"search":search, "username":username}).fetchone()[0]
                cleanedPosts = []
                postIds = []
                for post in results:
                    postIds.append(post[0])
                    onePost = []
                    onePost.append(post[0])
                    onePost.append(post[1])
                    onePost.append(post[2])
                    onePost.append(post[3])
                    if post[4] != None:
                        imgList = post[4].split(',')
                        onePost.append(imgList)
                    else:
                        onePost.append('')
                    onePost.append(post[5])
                    onePost.append(post[6])
                    cleanedPosts.append(onePost)
                postIds.sort()
                if len(postIds) > 0:
                    return render_template("diary.html", username=username, posts=cleanedPosts, search=find, postCount=numOfResults, lastPostId=postIds[0])
                else:
                    return render_template("diary.html", username=username, posts=cleanedPosts, postCount=numOfResults, search=find)
            else:
                session['diary'] = [username, search]
                results = db.execute("SELECT * FROM posts WHERE author= :username AND privacy='public' AND (title LIKE :search OR publishdate LIKE :search) ORDER by id DESC LIMIT 5", {"username":username, "search":search}).fetchall()
                numOfResults = db.execute("SELECT COUNT(*) FROM posts WHERE author= :username AND privacy='public' AND (title LIKE :search OR publishdate LIKE :search)", {"search":search, "username":username}).fetchone()[0]
                cleanedPosts = []
                postIds = []
                for post in results:
                    postIds.append(post[0])
                    onePost = []
                    onePost.append(post[0])
                    onePost.append(post[1])
                    onePost.append(post[2])
                    onePost.append(post[3])
                    if post[4] != None:
                        imgList = post[4].split(',')
                        onePost.append(imgList)
                    else:
                        onePost.append('')
                    onePost.append(post[5])
                    onePost.append(post[6])
                    cleanedPosts.append(onePost)
                postIds.sort()
                if len(postIds) > 0:
                    return render_template("diary.html", username=username, posts=cleanedPosts, search=find, postCount=numOfResults, lastPostId=postIds[0])
                else:
                    return render_template("diary.html", username=username, posts=cleanedPosts, search=find, postCount=numOfResults)
        else:
            if session.get("username") == username:
                session['diary'] = [username, None]
                posts = db.execute("SELECT * FROM posts WHERE author= :username ORDER by id DESC LIMIT 5", {"username":username}).fetchall()
                numOfPosts = db.execute("SELECT COUNT(*) FROM posts WHERE author= :username", {"username":username}).fetchone()[0]
                cleanedPosts = []
                postIds = []
                for post in posts:
                    postIds.append(post[0])
                    onePost = []
                    onePost.append(post[0])
                    onePost.append(post[1])
                    onePost.append(post[2])
                    onePost.append(post[3])
                    if post[4] != None:
                        imgList = post[4].split(',')
                        onePost.append(imgList)
                    else:
                        onePost.append('')
                    onePost.append(post[5])
                    onePost.append(post[6])
                    cleanedPosts.append(onePost)
                postIds.sort()
                if len(postIds) > 0:
                    return render_template("diary.html", username=username, posts=cleanedPosts, postCount=numOfPosts, lastPostId=postIds[0])
                else:
                    return render_template("diary.html", username=username, posts=cleanedPosts, postCount=numOfPosts)
            else:
                session['diary'] = [username, None]
                posts = db.execute("SELECT * FROM posts WHERE author= :username AND privacy='public' ORDER by id DESC LIMIT 5", {"username":username}).fetchall()
                numOfPosts = db.execute("SELECT COUNT(*) FROM posts WHERE author= :username AND privacy='public'", {"username":username}).fetchone()[0]
                cleanedPosts = []
                postIds = []
                for post in posts:
                    postIds.append(post[0])
                    onePost = []
                    onePost.append(post[0])
                    onePost.append(post[1])
                    onePost.append(post[2])
                    onePost.append(post[3])
                    if post[4] != None:
                        imgList = post[4].split(',')
                        onePost.append(imgList)
                    else:
                        onePost.append('')
                    onePost.append(post[5])
                    onePost.append(post[6])
                    cleanedPosts.append(onePost)
                postIds.sort()
                if len(postIds) > 0:
                    return render_template("diary.html", username=username, posts=cleanedPosts, postCount=numOfPosts, lastPostId=postIds[0])
                else:
                    return render_template("diary.html", username=username, posts=cleanedPosts, postCount=numOfPosts)
    else:
        return redirect("/")

@socketio.on('getMorePostsDiary')
def getMorePostsDiary(data):
    if session['diary'][1] == None:
        lastPostId = data['lastPostId']
        user = session.get('diary')[0]
        if user == session.get('username'):
            posts = db.execute("SELECT * FROM posts WHERE id < :lastPostId AND author= :username ORDER by id DESC LIMIT 5", {"username":user, "lastPostId":lastPostId}).fetchall()
            postCount = db.execute("SELECT COUNT(*) FROM posts WHERE id < :lastPostId AND author= :username", {"username":user, "lastPostId":lastPostId}).fetchone()[0]
        else:
            posts = db.execute("SELECT * FROM posts WHERE id < :lastPostId AND author= :username AND privacy='public' ORDER by id DESC LIMIT 5", {"username":user, "lastPostId":lastPostId}).fetchall()
            postCount = db.execute("SELECT COUNT(*) FROM posts WHERE id < :lastPostId AND author= :username AND privacy='public'", {"username":user, "lastPostId":lastPostId}).fetchone()[0]
        cleanedPosts = []
        postIds = []
        for post in posts:
            postIds.append(post[0])
            onePost = []
            onePost.append(post[0])
            onePost.append(post[1])
            onePost.append(post[2])
            onePost.append(post[3])
            if post[4] != None:
                imgList = post[4].split(',')
                onePost.append(imgList)
            else:
                onePost.append('')
            onePost.append(post[5])
            onePost.append(post[6])
            cleanedPosts.append(onePost)
        postIds.sort()
        lastPostId = postIds[0]
        emit('newPostsDiary', {'posts':cleanedPosts, 'currentUser':session.get('username'), "numOfPostsLeft":postCount, "lastPostId":lastPostId})
    else:
        lastPostId = data['lastPostId']
        user = session.get('diary')[0]
        search = session.get('diary')[1]
        if user == session.get('username'):
            posts = db.execute("SELECT * FROM posts WHERE id < :lastPostId AND author= :username AND (publishdate LIKE :search OR title LIKE :search) ORDER by id DESC LIMIT 5", {"username":user, "lastPostId":lastPostId, "search":search}).fetchall()
            postCount = db.execute("SELECT COUNT(*) FROM posts WHERE id < :lastPostId AND author= :username AND (publishdate LIKE :search OR title LIKE :search)", {"username":user, "lastPostId":lastPostId, "search":search}).fetchone()[0]
        else:
            posts = db.execute("SELECT * FROM posts WHERE id < :lastPostId AND author= :username AND privacy='public' AND (publishdate LIKE :search OR title LIKE :search) ORDER by id DESC LIMIT 5", {"username":user, "lastPostId":lastPostId, "search":search}).fetchall()
            postCount = db.execute("SELECT COUNT(*) FROM posts WHERE id < :lastPostId AND author= :username AND privacy='public' AND (publishdate LIKE :search OR title LIKE :search)", {"username":user, "lastPostId":lastPostId, "search":search}).fetchone()[0]
        cleanedPosts = []
        postIds = []
        for post in posts:
            postIds.append(post[0])
            onePost = []
            onePost.append(post[0])
            onePost.append(post[1])
            onePost.append(post[2])
            onePost.append(post[3])
            if post[4] != None:
                imgList = post[4].split(',')
                onePost.append(imgList)
            else:
                onePost.append('')
            onePost.append(post[5])
            onePost.append(post[6])
            cleanedPosts.append(onePost)
        postIds.sort()
        lastPostId = postIds[0]
        emit('newPostsDiary', {'posts':cleanedPosts, 'currentUser':session.get('username'), "numOfPostsLeft":postCount, "lastPostId":lastPostId, "search":True})

@socketio.on('showedNewPostDiary')
def beReady():
    emit('newSeeMoreDiary')

@app.route("/edit", methods=["POST"])
def edit():
    if session.get('loggedIn'):
        postId = request.form.get("postId")
        post = db.execute("SELECT * FROM posts WHERE id= :id", {"id":postId}).fetchone()
        todayDate = datetime.now().strftime("%d-%m-%Y")
        cleanedPost = []
        cleanedPost.append(post[0])
        cleanedPost.append(post[1])
        cleanedPost.append(post[2])
        cleanedPost.append(post[3])
        if post[4] != None:
            imgList = post[4].split(',')
            cleanedPost.append(imgList)
        else:
            cleanedPost.append('')
        cleanedPost.append(post[5])
        cleanedPost.append(post[6])
        if post[2] == todayDate:
            return redirect("/write")
        else:
            return render_template("edit.html", post=cleanedPost)
    else:
        return redirect("/")

@app.route("/editPost", methods=["POST"])
def editPost():
    action = request.form.get("doSomething")
    info = action.split(',')
    if info[0] == 'deletePost':
        db.execute("DELETE FROM posts WHERE id= :id", {"id":info[1]})
        db.commit()
        return redirect("/diary/" + session.get("username"))
    else:
        privacy = request.form.get("privacy")
        db.execute("UPDATE posts SET privacy= :privacy WHERE id= :id", {"privacy":privacy, "id":info[0]})
        db.commit()
        return redirect("/diary/" + session.get('username'))
