import os, re, shutil, subprocess, tempfile, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox

BG="#09090d"; PANEL="#111118"; PANEL2="#191923"; BORDER="#292936"
FG="#eeeef5"; MUTED="#888897"; PURPLE="#9b7cff"; GREEN="#8de0b0"; RED="#ff8195"
KEYWORDS=set("and break do else elseif end false for function if in local nil not or repeat return then true until while".split())
BUILTINS=set("assert collectgarbage dofile error getmetatable ipairs load loadfile next pairs pcall print rawequal rawget rawlen rawset select setmetatable tonumber tostring type xpcall coroutine debug io math os package string table utf8".split())

class Tab:
    def __init__(self, parent, content="", path=None):
        self.path=path
        self.frame=ttk.Frame(parent)
        self.text=tk.Text(self.frame, bg=BG, fg=FG, insertbackground=PURPLE,
            selectbackground="#40345f", font=("Cascadia Code",10), undo=True,
            wrap="none", padx=16, pady=14, relief="flat", borderwidth=0)
        sy=ttk.Scrollbar(self.frame, orient="vertical", command=self.text.yview)
        sx=ttk.Scrollbar(self.frame, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.text.grid(row=0,column=0,sticky="nsew"); sy.grid(row=0,column=1,sticky="ns"); sx.grid(row=1,column=0,sticky="ew")
        self.frame.rowconfigure(0,weight=1); self.frame.columnconfigure(0,weight=1)
        for tag,color in [("kw","#c4a7ff"),("bi","#85c9ff"),("str","#a8dba8"),("com","#777787"),("num","#f2bd83"),("fn","#80d8d0")]:
            self.text.tag_configure(tag,foreground=color)
        self.text.insert("1.0",content)
        self.job=None
        self.text.bind("<KeyRelease>",self.schedule)
        self.highlight_all()
    def schedule(self,event=None):
        if self.job: self.text.after_cancel(self.job)
        self.job=self.text.after(180,self.highlight_current)
    def highlight_current(self):
        self.job=None
        line=self.text.index("insert").split(".")[0]
        self.highlight_line(int(line))
    def highlight_line(self,n):
        start=f"{n}.0"; end=f"{n}.end"
        for t in ("kw","bi","str","com","num","fn"): self.text.tag_remove(t,start,end)
        s=self.text.get(start,end)
        pats=[
          ("com",r"--.*$"),("str",r'"(?:\\.|[^"\\])*"|\\'(?:\\\\.|[^\\'\\\\])*\\''),
          ("num",r"\\b\\d+(?:\\.\\d+)?\\b"),("fn",r"\\b[A-Za-z_]\\w*(?=\\s*\\()"),
          ("kw",r"\\b(?:"+"|".join(map(re.escape,KEYWORDS))+r")\\b"),
          ("bi",r"\\b(?:"+"|".join(map(re.escape,BUILTINS))+r")\\b")]
        for tag,pat in pats:
            for m in re.finditer(pat,s): self.text.tag_add(tag,f"{n}.{m.start()}",f"{n}.{m.end()}")
    def highlight_all(self):
        self.line=1; self.total=int(self.text.index("end-1c").split(".")[0]); self.chunk()
    def chunk(self):
        stop=min(self.line+150,self.total+1)
        for n in range(self.line,stop): self.highlight_line(n)
        self.line=stop
        if self.line<=self.total: self.text.after(1,self.chunk)
    def content(self): return self.text.get("1.0","end-1c")

class Velora:
    def __init__(self,root):
        self.root=root; root.title("VELORA"); root.geometry("1160x740"); root.minsize(820,540); root.configure(bg=BG)
        self.tabs={}; self.count=0; self.proc=None
        st=ttk.Style(); st.theme_use("clam")
        st.configure("TFrame",background=BG)
        st.configure("TNotebook",background=BG,borderwidth=0,tabmargins=0)
        st.configure("TNotebook.Tab",background=PANEL,foreground=MUTED,padding=(15,9),borderwidth=0)
        st.map("TNotebook.Tab",background=[("selected",PANEL2)],foreground=[("selected",FG)])
        st.configure("TScrollbar",background=PANEL,troughcolor=BG,bordercolor=BG,arrowcolor=MUTED)
        self.header()
        wrap=tk.Frame(root,bg=BG); wrap.pack(fill="both",expand=True,padx=14,pady=(14,8))
        self.nb=ttk.Notebook(wrap); self.nb.pack(fill="both",expand=True)
        consolebox=tk.Frame(root,bg=PANEL,height=150,highlightbackground=BORDER,highlightthickness=1)
        consolebox.pack(fill="x",padx=14,pady=(0,10)); consolebox.pack_propagate(False)
        tk.Label(consolebox,text="  OUTPUT CONSOLE",bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(anchor="w",pady=(7,2))
        self.console=tk.Text(consolebox,bg="#0c0c12",fg="#c9c9d5",font=("Cascadia Code",9),relief="flat",height=5,state="disabled",padx=10,pady=6)
        self.console.pack(fill="both",expand=True,padx=1,pady=(0,1))
        self.console.tag_configure("error",foreground=RED); self.console.tag_configure("ok",foreground=GREEN); self.console.tag_configure("info",foreground=PURPLE)
        foot=tk.Frame(root,bg=PANEL,height=30); foot.pack(fill="x",side="bottom"); foot.pack_propagate(False)
        self.status=tk.Label(foot,text="READY · LOCAL LUA WORKSPACE",bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")); self.status.pack(side="left",padx=14)
        self.runtime=tk.Label(foot,text=self.runtime_text(),bg=PANEL,fg=GREEN if self.lua() else "#e9c77d",font=("Segoe UI",8)); self.runtime.pack(side="right",padx=14)
        self.new_tab(); self.log("VELORA workspace ready.","ok")
        self.log("Standalone editor. Run Lua uses a local Lua interpreter; no process injection or game attachment.","info")
        root.protocol("WM_DELETE_WINDOW",self.close)
    def button(self,p,t,cmd,accent=False):
        b=tk.Button(p,text=t,command=cmd,bg=("#7052d4" if accent else PANEL2),fg="white" if accent else FG,
            activebackground=PURPLE,activeforeground="white",relief="flat",bd=0,padx=13,pady=7,
            font=("Segoe UI",9,"bold"),cursor="hand2")
        return b
    def header(self):
        h=tk.Frame(self.root,bg=PANEL,height=58,highlightbackground=BORDER,highlightthickness=1); h.pack(fill="x"); h.pack_propagate(False)
        logo=tk.Frame(h,bg=PANEL); logo.pack(side="left",padx=20)
        tk.Label(logo,text="V",bg=PANEL,fg=PURPLE,font=("Segoe UI",20,"bold")).pack(side="left")
        tk.Label(logo,text="ELORA",bg=PANEL,fg=FG,font=("Segoe UI",15,"bold")).pack(side="left")
        tk.Label(h,text="SCRIPT WORKSPACE",bg=PANEL,fg=MUTED,font=("Segoe UI",8,"bold")).pack(side="left",padx=18)
        a=tk.Frame(h,bg=PANEL); a.pack(side="right",padx=12)
        for label,fn,accent in [("New",self.new_tab,False),("Open",self.open_file,False),("Save",self.save_file,False),("Run Lua",self.run,True),("Stop",self.stop,False)]:
            self.button(a,label,fn,accent).pack(side="left",padx=3)
    def lua(self): return shutil.which("lua") or shutil.which("luajit")
    def runtime_text(self): return "LUA RUNTIME DETECTED" if self.lua() else "LUA RUNTIME NOT FOUND"
    def current(self):
        return self.tabs.get(self.nb.select())
    def new_tab(self,content="",path=None):
        self.count+=1; t=Tab(self.nb,content,path); self.tabs[str(t.frame)]=t
        self.nb.add(t.frame,text=os.path.basename(path) if path else f"untitled-{self.count}.lua"); self.nb.select(t.frame)
    def open_file(self):
        p=filedialog.askopenfilename(filetypes=[("Lua/Luau","*.lua *.luau"),("Text","*.txt"),("All files","*.*")])
        if not p:return
        try:
            with open(p,"r",encoding="utf-8-sig",errors="replace") as f: data=f.read()
            self.new_tab(data,p); self.log(f"Opened {os.path.basename(p)} · {os.path.getsize(p):,} bytes","ok")
        except Exception as e: messagebox.showerror("VELORA",str(e))
    def save_file(self):
        t=self.current()
        if not t:return
        p=t.path or filedialog.asksaveasfilename(defaultextension=".lua",filetypes=[("Lua","*.lua"),("Luau","*.luau"),("All files","*.*")])
        if not p:return
        try:
            data=t.content()
            with open(p,"w",encoding="utf-8",newline="\\n") as f:f.write(data)
            t.path=p; self.nb.tab(t.frame,text=os.path.basename(p)); self.log(f"Saved {len(data):,} characters.","ok")
        except Exception as e:messagebox.showerror("VELORA",str(e))
    def log(self,s,tag=None):
        if not s:return
        self.console.configure(state="normal"); self.console.insert("end",s+"\\n",tag or ()); self.console.see("end"); self.console.configure(state="disabled")
    def run(self):
        t=self.current(); lua=self.lua()
        if not t:return
        if not lua:self.log("Lua runtime not found. Install Lua and add 'lua' to PATH for local execution.","error"); return
        src=t.content()
        if not src.strip():self.log("Current editor is empty.","error"); return
        self.stop()
        fd,p=tempfile.mkstemp(suffix=".lua",prefix="velora_"); os.close(fd)
        with open(p,"w",encoding="utf-8") as f:f.write(src)
        self.status.configure(text="RUNNING · LOCAL LUA WORKSPACE")
        self.log("Running script locally...","info")
        def worker():
            try:
                self.proc=subprocess.Popen([lua,p],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="replace")
                out,err=self.proc.communicate(); code=self.proc.returncode
                if out:self.root.after(0,lambda:self.log(out.rstrip(),"ok"))
                if err:self.root.after(0,lambda:self.log(err.rstrip(),"error"))
                self.root.after(0,lambda:self.log(f"Finished · exit code {code}","ok" if code==0 else "error"))
            except Exception as e:self.root.after(0,lambda:self.log(str(e),"error"))
            finally:
                try:os.remove(p)
                except OSError:pass
                self.root.after(0,lambda:self.status.configure(text="READY · LOCAL LUA WORKSPACE"))
        threading.Thread(target=worker,daemon=True).start()
    def stop(self):
        if self.proc and self.proc.poll() is None:self.proc.terminate(); self.log("Stop requested.","info")
    def close(self):
        self.stop(); self.root.destroy()

if __name__=="__main__":
    root=tk.Tk(); Velora(root); root.mainloop()
