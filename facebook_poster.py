import json, random, secrets, time, webbrowser, tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
import requests, threading, os
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

# ========== إعدادات تطبيق فيسبوك (عدّلها هنا) ==========
APP_ID = "1234567890"          # ⚠️ أدخل App ID
APP_SECRET = "abc123def456"    # ⚠️ أدخل App Secret
REDIRECT_URI = "http://localhost:5000/callback"
API_VERSION = "v19.0"
PERMISSIONS = "pages_show_list,pages_manage_posts"
TOKEN_FILE = "page_tokens.json"
LAST_POSTS_FILE = "last_posts.json"  # لتخزين آخر منشور لكل صفحة

class FacebookApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ناشر فيسبوك المتعدد - إدارة الصفحات")
        self.geometry("800x750")
        self.configure(bg="#f0f2f5")
        self.pages = []
        self.page_vars = []
        self.delay_seconds = tk.IntVar(value=30)
        self.last_posts = {}  # مفتاح: page_id, قيمة: post_id

        self.load_pages_from_file()
        self.load_last_posts()
        self.create_widgets()

    def load_pages_from_file(self):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                self.pages = json.load(f)
                self.pages = [p for p in self.pages if all(k in p for k in ("id","name","access_token"))]
        except FileNotFoundError:
            self.pages = []

    def save_pages_to_file(self):
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(self.pages, f, indent=2, ensure_ascii=False)

    def load_last_posts(self):
        try:
            with open(LAST_POSTS_FILE, "r", encoding="utf-8") as f:
                self.last_posts = json.load(f)
        except FileNotFoundError:
            self.last_posts = {}

    def save_last_posts(self):
        with open(LAST_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.last_posts, f, indent=2, ensure_ascii=False)

    def create_widgets(self):
        # شريط العنوان
        header = tk.Frame(self, bg="#1877f2", height=60)
        header.pack(fill="x")
        tk.Label(header, text="📢 ناشر فيسبوك المتعدد", font=("Arial", 18, "bold"),
                 fg="white", bg="#1877f2").pack(pady=10)

        if not self.pages:
            self.show_login_interface()
        else:
            self.show_posting_interface()

    def show_login_interface(self):
        self.login_frame = tk.Frame(self, bg="#f0f2f5")
        self.login_frame.pack(pady=40)
        tk.Label(self.login_frame, text="لم يتم ربط أي صفحات بعد",
                 font=("Arial", 14), bg="#f0f2f5").pack()
        tk.Label(self.login_frame, text="اضغط على الزر لتسجيل الدخول بحساب فيسبوك",
                 font=("Arial", 10), bg="#f0f2f5", fg="gray").pack(pady=5)
        self.login_btn = tk.Button(self.login_frame, text="🔐 تسجيل الدخول باستخدام فيسبوك",
                                   font=("Arial", 12, "bold"), bg="#42b72a", fg="white",
                                   padx=20, pady=8, bd=0, activebackground="#36a420",
                                   command=self.start_login)
        self.login_btn.pack(pady=15)
        self.status_lbl = tk.Label(self, text="", font=("Arial", 9), bg="#f0f2f5")
        self.status_lbl.pack()
        self.start_local_server()

    def start_local_server(self):
        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                if parsed.path == "/callback":
                    code = params.get("code", [None])[0]
                    state = params.get("state", [None])[0]
                    self.server.code = code
                    self.server.state = state
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"<html><body><h3>تم تسجيل الدخول بنجاح. يمكنك اغلاق هذه النافذة.</h3></body></html>")

        self.server = HTTPServer(("localhost", 5000), CallbackHandler)
        self.server.code = None
        self.server.state = None
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def start_login(self):
        self.login_btn.config(state="disabled", text="جارِ التوجيه...")
        state = secrets.token_urlsafe(16)
        self.oauth_state = state
        auth_url = (f"https://www.facebook.com/{API_VERSION}/dialog/oauth"
                    f"?client_id={APP_ID}&redirect_uri={REDIRECT_URI}"
                    f"&state={state}&scope={PERMISSIONS}")
        webbrowser.open(auth_url)
        self.status_lbl.config(text="تم فتح المتصفح. بعد الموافقة، انتظر قليلاً...")
        self.check_callback()

    def check_callback(self):
        if self.server.code is not None:
            code = self.server.code
            state = self.server.state
            if state != self.oauth_state:
                messagebox.showerror("خطأ", "حالة غير متطابقة (CSRF)")
                self.login_btn.config(state="normal", text="🔐 تسجيل الدخول باستخدام فيسبوك")
                return
            self.exchange_code_for_token(code)
        else:
            self.after(1000, self.check_callback)

    def exchange_code_for_token(self, code):
        self.status_lbl.config(text="جارِ الحصول على رمز الوصول...")
        token_url = f"https://graph.facebook.com/{API_VERSION}/oauth/access_token"
        params = {"client_id": APP_ID, "redirect_uri": REDIRECT_URI, "client_secret": APP_SECRET, "code": code}
        resp = requests.get(token_url, params=params)
        if resp.status_code != 200:
            messagebox.showerror("خطأ", f"فشل الحصول على رمز الوصول: {resp.text}")
            self.login_btn.config(state="normal", text="🔐 تسجيل الدخول باستخدام فيسبوك")
            return
        user_token = resp.json()["access_token"]

        ext_resp = requests.get(f"https://graph.facebook.com/{API_VERSION}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": APP_ID,
            "client_secret": APP_SECRET, "fb_exchange_token": user_token
        })
        long_token = ext_resp.json().get("access_token", user_token)

        pages_resp = requests.get(f"https://graph.facebook.com/{API_VERSION}/me/accounts", params={
            "access_token": long_token, "fields": "id,name,access_token"
        })
        if pages_resp.status_code == 200:
            self.pages = pages_resp.json().get("data", [])
            self.save_pages_to_file()
            messagebox.showinfo("نجاح", f"تم ربط {len(self.pages)} صفحات بنجاح.")
            self.refresh_interface()
        else:
            messagebox.showerror("خطأ", f"فشل جلب الصفحات: {pages_resp.text}")
            self.login_btn.config(state="normal", text="🔐 تسجيل الدخول باستخدام فيسبوك")

    def delete_account(self):
        if messagebox.askyesno("تأكيد", "هل أنت متأكد من حذف بيانات الحساب؟ ستحتاج إلى إعادة تسجيل الدخول."):
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)
            if os.path.exists(LAST_POSTS_FILE):
                os.remove(LAST_POSTS_FILE)
            self.pages = []
            self.last_posts = {}
            self.refresh_interface()

    def set_delay(self):
        new_delay = simpledialog.askinteger("مدة التأخير", "أدخل مدة الانتظار بين الصفحات (بالثواني):",
                                            initialvalue=self.delay_seconds.get(), minvalue=5, maxvalue=3600)
        if new_delay is not None:
            self.delay_seconds.set(new_delay)
            messagebox.showinfo("تم", f"تم تعيين التأخير إلى {new_delay} ثانية.")

    def delete_last_post(self, page_id):
        if page_id in self.last_posts:
            post_id = self.last_posts[page_id]
            page_token = None
            for p in self.pages:
                if p["id"] == page_id:
                    page_token = p["access_token"]
                    break
            if not page_token:
                messagebox.showerror("خطأ", "لم يتم العثور على رمز الصفحة.")
                return
            try:
                url = f"https://graph.facebook.com/{API_VERSION}/{post_id}"
                resp = requests.delete(url, params={"access_token": page_token})
                if resp.status_code == 200 or resp.json().get("success", False):
                    del self.last_posts[page_id]
                    self.save_last_posts()
                    messagebox.showinfo("تم", "تم حذف المنشور بنجاح.")
                    self.refresh_interface()
                else:
                    messagebox.showerror("خطأ", f"فشل الحذف: {resp.json()}")
            except Exception as e:
                messagebox.showerror("خطأ", str(e))
        else:
            messagebox.showinfo("تنبيه", "لا يوجد منشور سابق محفوظ لهذه الصفحة.")

    def refresh_interface(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.create_widgets()

    def show_posting_interface(self):
        # شريط أدوات
        toolbar = tk.Frame(self, bg="#ffffff", bd=0, highlightbackground="#ddd", highlightthickness=1)
        toolbar.pack(fill="x", padx=10, pady=(10,0))
        btn_style = {"font": ("Arial", 10), "bd": 0, "padx": 10, "pady": 5}

        tk.Button(toolbar, text="🗑️ حذف الحساب", fg="white", bg="#e74c3c", activebackground="#c0392b",
                  command=self.delete_account, **btn_style).pack(side="left", padx=2)
        tk.Button(toolbar, text="⏱️ تعديل التأخير", command=self.set_delay, bg="#ecf0f1", **btn_style).pack(side="left", padx=2)

        # جسم الواجهة
        main_frame = tk.Frame(self, bg="#f0f2f5")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # منطقة الرسالة
        msg_frame = tk.LabelFrame(main_frame, text="📝 نص المنشور", font=("Arial", 10, "bold"),
                                  bg="#ffffff", fg="#333", padx=10, pady=10)
        msg_frame.pack(fill="both", expand=False, pady=(0,10))
        self.message_text = scrolledtext.ScrolledText(msg_frame, height=5, font=("Tahoma", 11))
        self.message_text.pack(fill="both", expand=True)

        # قائمة الصفحات مع أزرار الحذف
        pages_frame = tk.LabelFrame(main_frame, text="📄 صفحاتك", font=("Arial", 10, "bold"),
                                    bg="#ffffff", fg="#333", padx=10, pady=10)
        pages_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(pages_frame, bg="#ffffff", height=180)
        scrollbar = tk.Scrollbar(pages_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg="#ffffff")
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.page_vars.clear()
        self.page_widgets = []  # لحفظ مراجع الأزرار

        for page in self.pages:
            pid = page["id"]
            # إطار لكل صفحة
            row_frame = tk.Frame(self.scrollable_frame, bg="#ffffff", pady=2)
            row_frame.pack(fill="x", anchor="w")

            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(row_frame, text=page["name"], variable=var,
                                font=("Tahoma", 10), bg="#ffffff", anchor="w")
            cb.pack(side="left", padx=(0,20))

            # زر حذف آخر منشور
            delete_btn = tk.Button(row_frame, text="🗑️ حذف آخر منشور", font=("Arial", 8),
                                   bg="#ffcccc", fg="black", bd=0, padx=5,
                                   command=lambda p=pid: self.delete_last_post(p))
            # تعطيل الزر إذا لم يكن هناك منشور سابق
            if pid not in self.last_posts:
                delete_btn.config(state="disabled", text="لا يوجد")
            delete_btn.pack(side="right", padx=5)

            self.page_vars.append((var, page))
            self.page_widgets.append(delete_btn)

        # زر النشر الرئيسي
        btn_frame = tk.Frame(main_frame, bg="#f0f2f5")
        btn_frame.pack(fill="x", pady=10)
        self.post_btn = tk.Button(btn_frame, text="🚀 نشر الآن", font=("Arial", 14, "bold"),
                                  bg="#1877f2", fg="white", padx=30, pady=10, bd=0,
                                  activebackground="#166fe5", command=self.start_posting)
        self.post_btn.pack()

        # شريط الحالة
        self.status_label = tk.Label(self, text="✅ جاهز", font=("Arial", 10), bg="#f0f2f5", fg="green")
        self.status_label.pack(pady=5)

    def start_posting(self):
        msg = self.message_text.get("1.0", tk.END).strip()
        if not msg:
            messagebox.showwarning("تحذير", "يرجى كتابة نص المنشور.")
            return
        selected = [p for var, p in self.page_vars if var.get()]
        if not selected:
            messagebox.showwarning("تحذير", "لم تحدد أي صفحة.")
            return

        self.post_btn.config(state="disabled", text="⏳ جارِ النشر...")
        self.status_label.config(text="⏳ جارِ النشر...", fg="orange")
        threading.Thread(target=self.post_to_pages, args=(msg, selected), daemon=True).start()

    def post_to_pages(self, msg, selected):
        total = len(selected)
        delay = self.delay_seconds.get()
        for idx, page in enumerate(selected):
            pid = page["id"]
            full_msg = f"{msg}\n- {page['name']}"
            try:
                resp = requests.post(
                    f"https://graph.facebook.com/{API_VERSION}/{pid}/feed",
                    params={"message": full_msg, "access_token": page["access_token"]},
                    timeout=15
                )
                if resp.status_code == 200:
                    post_id = resp.json().get("id")
                    # تخزين آخر منشور
                    self.last_posts[pid] = post_id
                    self.save_last_posts()
                    status_text = f"✔️ تم النشر على {page['name']}"
                else:
                    err = resp.json().get('error', {}).get('message', '')
                    status_text = f"❌ فشل {page['name']}: {err}"
            except Exception as e:
                status_text = f"❌ خطأ في {page['name']}: {str(e)}"

            self.after(0, self.update_status, status_text, idx+1, total)
            if idx < total - 1:
                time.sleep(delay)
        self.after(0, self.posting_finished)

    def update_status(self, text, cur, total):
        self.status_label.config(text=f"({cur}/{total}) {text}", fg="black")
        # تحديث أزرار الحذف بعد النشر
        self.refresh_delete_buttons()

    def refresh_delete_buttons(self):
        if hasattr(self, 'page_widgets'):
            for i, page in enumerate(self.pages):
                pid = page["id"]
                if i < len(self.page_widgets):
                    btn = self.page_widgets[i]
                    if pid in self.last_posts:
                        btn.config(state="normal", text="🗑️ حذف آخر منشور")
                    else:
                        btn.config(state="disabled", text="لا يوجد")

    def posting_finished(self):
        self.post_btn.config(state="normal", text="🚀 نشر الآن")
        self.status_label.config(text="✅ تم الانتهاء من النشر على جميع الصفحات المحددة.", fg="green")
        messagebox.showinfo("اكتمل", "تم الانتهاء من النشر.")
        self.refresh_delete_buttons()

if __name__ == "__main__":
    app = FacebookApp()
    app.mainloop()