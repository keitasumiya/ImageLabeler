import os
import sys
import json
import csv
import shutil
from tkinter import Tk, Frame, Button, Canvas, Checkbutton, IntVar, Label, Entry, filedialog
from PIL import Image, ImageTk

bg_color = "#c7c7c7"

class ImageLabelerApp:
    def __init__(self, master):
        self.master = master
        self.master.title('Image Labeler')
        # settings.json 読み込み (PyInstaller対応)
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
        else:
            base_dir = os.path.dirname(__file__)
        settings_path = os.path.join(base_dir, 'settings.json')
        with open(settings_path, 'r') as f:
            self.settings = json.load(f)
        # data_path 更新
        dp = self.settings.get('data_path', '')
        if not os.path.isdir(dp):
            dp = filedialog.askdirectory(title='Select data_path directory')
            self.settings['data_path'] = dp
            if not getattr(sys, 'frozen', False):
                with open(settings_path, 'w') as f:
                    json.dump(self.settings, f, indent=2)
        self.data_path = dp

        # ディレクトリ準備とラベル同期
        self.ensure_directories()
        self.labels = self.sync_labels_from_dirs()

        # UI状態変数
        self.include_labeled = IntVar(value=1)
        self.images = []
        self.idx = 0
        self.current_pil = None

        # 初期 unlabeled 総数を保持
        self.refresh_image_list()
        self.unlabeled_total = len(self.images)

        # UI構築
        self.build_ui()
        self.show_image()

    def ensure_directories(self):
        dp = self.data_path
        for key in ('unlabeled_dir', 'clear_dir', 'cloudy_dir'):
            os.makedirs(os.path.join(dp, self.settings[key]), exist_ok=True)
        # ルートに画像があり unlabeled ディレクトリが空なら移動
        root_imgs = [f for f in os.listdir(dp) if f.lower().endswith(('.png','.jpg','.jpeg'))]
        unlabeled_dir = os.path.join(dp, self.settings['unlabeled_dir'])
        if root_imgs and os.path.isdir(unlabeled_dir) and not os.listdir(unlabeled_dir):
            for fn in root_imgs:
                shutil.move(os.path.join(dp, fn), unlabeled_dir)

    def sync_labels_from_dirs(self):
        dp = self.data_path
        mapping = []
        for subdir, lbl in [(self.settings['unlabeled_dir'], ''),
                            (self.settings['clear_dir'], 'clear'),
                            (self.settings['cloudy_dir'], 'cloudy')]:
            path = os.path.join(dp, subdir)
            for fn in os.listdir(path):
                if fn.lower().endswith(('.png','.jpg','.jpeg')):
                    mapping.append((fn, lbl))
        mapping.sort(key=lambda x: x[0])
        # CSV書き込み
        csv_path = os.path.join(dp, self.settings['csv'])
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            for fn, lbl in mapping:
                writer.writerow([fn, lbl])
        return {fn: lbl for fn, lbl in mapping}

    def save_labels(self):
        # ディレクトリ状態を再スキャンして CSV を更新
        self.labels = self.sync_labels_from_dirs()

    def refresh_image_list(self):
        dirs = ['unlabeled_dir']
        if self.include_labeled.get():
            dirs = ['unlabeled_dir', 'clear_dir', 'cloudy_dir']
        imgs = []
        for key in dirs:
            p = os.path.join(self.data_path, self.settings[key])
            for fn in os.listdir(p):
                if fn.lower().endswith(('.png','.jpg','.jpeg')):
                    imgs.append((fn, p))
        self.images = sorted(imgs, key=lambda x: x[0])

    def build_ui(self):
        # グリッド設定: Canvas が伸縮可能
        self.master.rowconfigure(2, weight=1)
        self.master.columnconfigure(1, weight=1)
        # 上段: Back ボタン、カウント
        Button(self.master, text='Back', command=self.on_back, highlightbackground=bg_color).grid(row=0, column=1, pady=(10,0))
        # self.count_label = Label(self.master, text='0/0')
        # self.count_label.grid(row=0, column=2, sticky='e', padx=10)
        top_right = Frame(self.master)
        top_right.grid(row=0,column=1,columnspan=3,sticky='e',padx=10)
        vcmd = (self.master.register(self._validate_digit), '%S')
        self.jump_entry = Entry(top_right, width=5, validate='key', validatecommand=vcmd, highlightbackground=bg_color)
        # self.jump_entry = Entry(top_right,width=5)
        self.jump_entry.grid(row=0,column=0)
        # Button(top_right,text='→',command=self.on_jump).grid(row=0,column=1,padx=5)
        self.jump_button = Button(top_right, text='→', command=self.on_jump, highlightbackground=bg_color)
        self.jump_button.grid(row=0, column=1, padx=5)
        self.count_label = Label(top_right, text='0/0')
        self.count_label.grid(row=0, column=2, sticky='e', padx=10)

        self.filename_label = Label(self.master, text='', font=('Arial', 12))
        self.filename_label.grid(row=1, column=1)
        Checkbutton(self.master, text='include labeled', variable=self.include_labeled,
                    command=self.on_toggle_include).grid(row=1, column=2, sticky='ne', padx=10, pady=(0,10))

        # 中央: Cloudy, Canvas, Clear
        Button(self.master, text='Cloudy', command=self.on_cloudy, highlightbackground=bg_color).grid(row=2, column=0, padx=10)
        self.canvas = Canvas(self.master, bg='black')
        self.canvas.grid(row=2, column=1, sticky='nsew')
        Button(self.master, text='Clear', command=self.on_clear, highlightbackground=bg_color).grid(row=2, column=2, padx=10)
        self.canvas.bind('<Configure>', self.on_canvas_resize)
        # 下段: Next
        Button(self.master, text='Next', command=self.on_next, highlightbackground=bg_color).grid(row=3, column=1, pady=(0,10))
        # グローバルクリックでEntry外クリックを検知
        self.master.bind_all('<Button-1>',self.on_click_anywhere)
        # 矢印キー対応（フォーカス判定あり）
        self.master.bind('<Up>',self._bind_arrow(self.on_back))
        self.master.bind('<Down>',self._bind_arrow(self.on_next))
        self.master.bind('<Left>',self._bind_arrow(self.on_cloudy))
        self.master.bind('<Right>',self._bind_arrow(self.on_clear))
        # 初期 Jump ボタン状態更新
        self._update_jump_state()

    def _update_jump_state(self):
        # include_labeled がオフなら Jump 非活性
        if self.include_labeled.get():
            self.jump_button.config(state='normal')
        else:
            self.jump_button.config(state='disabled')

    def _validate_digit(self, char):
        # 入力された文字が数字なら許可
        return char.isdigit()

    def on_click_anywhere(self,event):
        # Entry以外をクリックしたらEntryからフォーカスを外す
        if event.widget is not self.jump_entry:
            self.master.focus_set()

    def _bind_arrow(self,func):
        # arrow key binding wrapper
        def handler(event):
            if self.jump_entry == self.master.focus_get():
                return
            func()
        return handler

    def show_image(self):
        self.canvas.delete('all')
        # total 表示: include_labeled OFF -> fixed unlabeled_total, ON -> len(images)
        total = len(self.images) if self.include_labeled.get() else self.unlabeled_total
        # current 表示
        if self.idx < len(self.images):
            current = self.idx + 1
        else:
            current = total
        current = max(1, current) if total > 0 else 0
        self.count_label.config(text=f'{current}/{total}')

        # All labeled
        if self.idx < 0 or self.idx >= len(self.images):
            self.filename_label.config(text='')
            self.canvas.create_text(self.canvas.winfo_width()/2,
                                    self.canvas.winfo_height()/2,
                                    text='All labeled', fill='white', font=('Arial', 24))
            self.current_pil = None
            return

        fn, path = self.images[self.idx]
        self.filename_label.config(text=fn)
        self.current_pil = Image.open(os.path.join(path, fn))
        self.render_image()

    def render_image(self):
        if not self.current_pil:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        pil = self.current_pil.copy()
        pil.thumbnail((cw, ch), Image.ANTIALIAS)
        self.tkimg = ImageTk.PhotoImage(pil)
        self.canvas.delete('IMG')
        self.canvas.create_image((cw - pil.width)//2,
                                 (ch - pil.height)//2,
                                 anchor='nw', image=self.tkimg, tags='IMG')
        # ラベルオーバーレイ
        fn = self.images[self.idx][0]
        lbl = self.labels.get(fn, '')
        if lbl:
            rw, rh = 80, 30
            x = (cw - pil.width)//2 + pil.width - rw - 5
            y = (ch - pil.height)//2 + 5
            self.canvas.create_rectangle(x, y, x + rw, y + rh,
                                         fill='grey', outline='black')
            self.canvas.create_text(x + rw/2, y + rh/2,
                                    text=lbl, fill='white', font=('Arial', 12))

    def on_canvas_resize(self, event):
        self.render_image()

    def on_jump(self):
        if not self.include_labeled.get():
            return
        try:
            n = int(self.jump_entry.get()) - 1
        except ValueError:
            return
        if n < 0:
            # self.idx = 0
            return
        elif n >= len(self.images):
            # self.idx = len(self.images)
            return
        else:
            self.idx = n
        self.show_image()

    def on_toggle_include(self):
        # include_labeled 切替時に画像リスト更新。unlabeled_total は変更せず固定
        # self.idx = 0
        # self.refresh_image_list()
        # self.unlabeled_total = len(self.images)
        # self.show_image()
        if self.include_labeled.get():
            current_tmp = ""
            if len(self.images) != 0:
                current_tmp = self.images[self.idx]
            self.refresh_image_list()
            self._update_jump_state()
            try:
                self.idx = self.images.index(current_tmp)
            except ValueError:
                self.idx = 0
                print("Not Found")
            self.show_image()
        else:
            self.idx = 0
            self.refresh_image_list()
            self._update_jump_state()
            self.unlabeled_total = len(self.images)
            self.show_image()

    def on_back(self):
        # 6-1: back (↑) 1つ前
        if self.include_labeled.get():
            if self.idx > 0:
                self.idx -= 1
            self.show_image()
        else:
            unlabeled_dir = os.path.join(self.data_path, self.settings['unlabeled_dir'])
            full_path_tmp = os.path.join(unlabeled_dir, self.images[self.idx - 1][0])
            if os.path.isfile(full_path_tmp):
                self.idx -= 1
            self.show_image()

    def on_next(self):
        # 6-2: next (↓) 1つ次
        total_imgs = len(self.images)
        if self.idx < total_imgs - 1:
            self.idx += 1
        else:
            # ステップ8: 最後の次は All labeled
            self.idx += 1
        self.show_image()

    def on_cloudy(self):
        # 6-3: cloudy (←)
        if 0 <= self.idx < len(self.images):
            fn, old = self.images[self.idx]
            self.labels[fn] = 'cloudy'
            dst = os.path.join(self.data_path, self.settings['cloudy_dir'], fn)
            shutil.move(os.path.join(old, fn), dst)
            self.save_labels()
            # 常に次へ
            self.idx += 1
        if self.include_labeled.get():
            self.refresh_image_list()
        # self.refresh_image_list()
        self.show_image()

    def on_clear(self):
        # 6-4: clear (→)
        if 0 <= self.idx < len(self.images):
            fn, old = self.images[self.idx]
            self.labels[fn] = 'clear'
            dst = os.path.join(self.data_path, self.settings['clear_dir'], fn)
            shutil.move(os.path.join(old, fn), dst)
            self.save_labels()
            self.idx += 1
        if self.include_labeled.get():
            self.refresh_image_list()
        # self.refresh_image_list()
        self.show_image()

if __name__ == '__main__':
    root = Tk()
    app = ImageLabelerApp(root)
    def maximize():
        try:
            root.state('zoomed')       # Windows
        except:
            try:
                root.attributes('-zoomed', True)  # Linux
            except:
                w = root.winfo_screenwidth()
                h = root.winfo_screenheight()
                root.geometry(f"{w}x{h}+0+0")
    root.after(50, maximize)
    root.after(200, maximize)

    def bring_to_front():
        try:
            root.lift()
            root.focus_force()
            root.attributes('-topmost', True)
            root.update()
            root.attributes('-topmost', False)
        except Exception:
            pass
    root.after(100, bring_to_front)
    root.after(500, bring_to_front)
    root.mainloop()
