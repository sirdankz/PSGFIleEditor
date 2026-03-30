import os
import sys
import io
import base64
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from base64 import b64decode

EMBEDDED_TGA = {
    # "0x0000137003e38818.psg": "BASE64_TGA_DATA_HERE",
}

EMBEDDED_PNGS = {
    # "0x0000137003e38818.psg": "BASE64_PNG_DATA_HERE",
}

FIX_METADATA = {
    # "0x0000137003e38818.psg": {
    #     "header": "0000000800EB0008...",
    #     "tail": "54B011F4..."
    # },
}


class ToggleSwitch(tk.Canvas):
    def __init__(self, master, variable, **kwargs):
        super().__init__(
            master,
            width=50,
            height=24,
            highlightthickness=0,
            bg=master["bg"],
            **kwargs
        )
        self.variable = variable
        self.bind("<Button-1>", self.toggle)
        self.draw()

    def toggle(self, event=None):
        self.variable.set(not self.variable.get())
        self.draw()

    def draw(self):
        self.delete("all")
        on = self.variable.get()
        bg = "#4caf50" if on else "#444"
        knob = "#fff"
        self.create_rectangle(2, 2, 48, 22, fill=bg, outline=bg, width=2)
        self.create_oval(
            26 if on else 2,
            2,
            46 if on else 22,
            22,
            fill=knob,
            outline=knob
        )


class PSGEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PSG Texture & Deck Editor")
        self.root.configure(bg="#2e2e2e")

        self.psg_folder = ""
        self.png_folder = ""
        self.dds_files = []

        self.matching_psgs = []
        self.psg_to_png = {}
        self.tk_img = None

        self.patched_png_folder = os.path.join(os.getcwd(), "patched_pngs")
        self.exported_tga_folder = os.path.join(os.getcwd(), "exported_tga_files")

        self.backup_enabled = tk.BooleanVar(value=True)
        self.use_embedded_pngs = tk.BooleanVar(value=True)
        self.show_original_only = tk.BooleanVar(value=False)

        self.ref_psg_folder = ""

        self.setup_ui()

    def setup_ui(self):
        frm = tk.Frame(self.root, bg="#2e2e2e")
        frm.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        tk.Button(
            frm,
            text="1. Select PSG Folder",
            command=self.select_psg_folder,
            bg="#444",
            fg="#fff"
        ).grid(row=0, column=0, sticky="ew")
        self.lbl_psg_folder = tk.Label(frm, text="No PSG folder", fg="#0af", bg="#2e2e2e")
        self.lbl_psg_folder.grid(row=0, column=1, sticky="w")

        tk.Button(
            frm,
            text="2. Select PNG Folder",
            command=self.select_png_folder,
            bg="#444",
            fg="#fff"
        ).grid(row=1, column=0, sticky="ew")
        self.lbl_png_folder = tk.Label(frm, text="No PNG folder", fg="#0af", bg="#2e2e2e")
        self.lbl_png_folder.grid(row=1, column=1, sticky="w")

        tk.Button(
            frm,
            text="3. Select DDS or PSG File(s)",
            command=self.select_dds_files,
            bg="#444",
            fg="#fff"
        ).grid(row=2, column=0, sticky="ew")
        self.lbl_dds_info = tk.Label(frm, text="No DDS/PSG selected", fg="#0f0", bg="#2e2e2e")
        self.lbl_dds_info.grid(row=2, column=1, sticky="w")

        list_frame = tk.Frame(frm)
        list_frame.grid(row=3, column=0, rowspan=6, sticky="ns")
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)

        self.lst_psgs = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            width=40,
            yscrollcommand=scrollbar.set,
            bg="#1e1e1e",
            fg="white"
        )
        scrollbar.config(command=self.lst_psgs.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.lst_psgs.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.lst_psgs.bind("<<ListboxSelect>>", self.update_preview)

        self.lbl_preview = tk.Label(
            frm,
            text="Select a PSG to preview PNG",
            width=40,
            height=20,
            relief=tk.SUNKEN,
            bg="#1e1e1e",
            fg="white"
        )
        self.lbl_preview.grid(row=3, column=1, rowspan=6, sticky="nsew", padx=(10, 0))

        tk.Button(
            frm,
            text="4. Select Reference PSG Folder",
            command=self.select_ref_psg_folder,
            bg="#444",
            fg="#fff"
        ).grid(row=9, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.lbl_ref_folder = tk.Label(
            frm,
            text="No Reference PSG folder",
            fg="#aaa",
            bg="#2e2e2e"
        )
        self.lbl_ref_folder.grid(row=10, column=0, columnspan=2, sticky="w")

        tk.Button(
            frm,
            text="Restore Selected PSG(s)",
            command=self.restore_selected_psgs,
            bg="#663",
            fg="#fff"
        ).grid(row=11, column=0, columnspan=2, sticky="ew", pady=(2, 0))

        tk.Button(
            frm,
            text="Restore All PSGs from Reference",
            command=self.restore_all_psgs_confirm,
            bg="#822",
            fg="#fff"
        ).grid(row=12, column=0, columnspan=2, sticky="ew", pady=(2, 10))

        self.add_toggle(frm, "Show Embedded PNGs", self.use_embedded_pngs, row=13)
        self.add_toggle(frm, "Show Original PNGs Only", self.show_original_only, row=14)
        self.add_toggle(frm, "Backup original PSG", self.backup_enabled, row=15)

        tk.Button(
            frm,
            text="Patch Selected PSGs",
            command=self.apply_patch,
            bg="#444",
            fg="#fff"
        ).grid(row=16, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        tk.Button(
            frm,
            text="Export Selected PSG(s) to TGA",
            command=self.export_selected_tgas,
            bg="#446",
            fg="#fff"
        ).grid(row=17, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        self.txt = tk.Text(
            frm,
            height=10,
            width=100,
            bg="#1e1e1e",
            fg="white",
            insertbackground="white"
        )
        self.txt.grid(row=18, column=0, columnspan=2, pady=(10, 0), sticky="nsew")

        frm.grid_rowconfigure(18, weight=1)
        frm.grid_columnconfigure(1, weight=1)

    def add_toggle(self, parent, label, var, row):
        lbl = tk.Label(parent, text=label, fg="white", bg="#2e2e2e")
        lbl.grid(row=row, column=0, sticky="w", pady=2)
        ToggleSwitch(parent, variable=var).grid(row=row, column=1, sticky="w")

    def log(self, msg):
        self.txt.insert(tk.END, msg + "\n")
        self.txt.see(tk.END)

    def select_psg_folder(self):
        path = filedialog.askdirectory(title="Select PSG folder")
        if path:
            self.psg_folder = path
            self.lbl_psg_folder.config(text=path)
            self.update_matching_list()

    def select_png_folder(self):
        path = filedialog.askdirectory(title="Select PNG folder")
        if path:
            self.png_folder = path
            self.lbl_png_folder.config(text=path)
            self.update_matching_list()

    def select_dds_files(self):
        files = filedialog.askopenfilenames(
            title="Select DDS or PSG files",
            filetypes=[
                ("DDS/PSG files", "*.dds *.psg"),
                ("DDS files", "*.dds"),
                ("PSG files", "*.psg"),
                ("All files", "*.*"),
            ]
        )
        if files:
            self.dds_files = list(files)
            self.lbl_dds_info.config(text=f"{len(files)} file(s) selected")

    def select_ref_psg_folder(self):
        path = filedialog.askdirectory(title="Select Reference PSG Folder")
        if path:
            self.ref_psg_folder = path
            self.lbl_ref_folder.config(text=path)

    def restore_selected_psgs(self):
        if not self.ref_psg_folder:
            messagebox.showwarning("Missing Folder", "Select a reference PSG folder first.")
            return

        if not self.lst_psgs.curselection():
            messagebox.showwarning("No Selection", "Select one or more PSGs to restore.")
            return

        for idx in self.lst_psgs.curselection():
            psg_name = self.matching_psgs[idx]
            ref_path = os.path.join(self.ref_psg_folder, psg_name)
            tgt_path = os.path.join(self.psg_folder, psg_name)

            if os.path.exists(ref_path):
                try:
                    with open(ref_path, "rb") as src, open(tgt_path, "wb") as dst:
                        dst.write(src.read())
                    self.log(f"Restored: {psg_name}")
                except Exception as e:
                    self.log(f"Failed to restore {psg_name}: {e}")
            else:
                self.log(f"Missing in reference folder: {psg_name}")

        self.update_matching_list()

    def restore_all_psgs_confirm(self):
        if messagebox.askyesno(
            "Confirm Restore",
            "Are you sure you want to overwrite all PSGs in the target folder with files from the reference folder?"
        ):
            self.restore_all_psgs()

    def restore_all_psgs(self):
        if not self.ref_psg_folder:
            messagebox.showwarning("Missing Folder", "Select a reference PSG folder first.")
            return

        restored = 0
        for fname in os.listdir(self.ref_psg_folder):
            if not fname.lower().endswith(".psg"):
                continue

            ref_path = os.path.join(self.ref_psg_folder, fname)
            tgt_path = os.path.join(self.psg_folder, fname)

            if os.path.exists(tgt_path):
                try:
                    with open(ref_path, "rb") as src, open(tgt_path, "wb") as dst:
                        dst.write(src.read())
                    self.log(f"Restored: {fname}")
                    restored += 1
                except Exception as e:
                    self.log(f"Failed to restore {fname}: {e}")

        self.log(f"✔ Restored {restored} PSG(s).")
        self.update_matching_list()

    def update_matching_list(self):
        self.lst_psgs.delete(0, tk.END)
        self.matching_psgs.clear()
        self.psg_to_png.clear()
        self.lbl_preview.config(image="", text="Select a PSG to preview PNG")

        if not self.psg_folder:
            return

        embedded_basenames = {
            os.path.splitext(k)[0]
            for k in (set(EMBEDDED_PNGS.keys()) | set(EMBEDDED_TGA.keys()))
        }

        psg_files = [f for f in os.listdir(self.psg_folder) if f.lower().endswith(".psg")]
        for psg in psg_files:
            base = os.path.splitext(psg)[0]
            if base in embedded_basenames:
                self.matching_psgs.append(psg)

        self.matching_psgs.sort()
        for psg in self.matching_psgs:
            self.lst_psgs.insert(tk.END, psg)

    def update_preview(self, event=None):
        sel = self.lst_psgs.curselection()
        if not sel:
            self.lbl_preview.config(image="", text="Select a PSG to preview PNG")
            return

        psg_name = self.matching_psgs[sel[0]]
        base = os.path.splitext(psg_name)[0]

        if self.show_original_only.get():
            if psg_name in EMBEDDED_PNGS:
                try:
                    img = Image.open(io.BytesIO(b64decode(EMBEDDED_PNGS[psg_name])))
                    img = img.convert("RGB")
                    img.thumbnail((300, 300))
                    self.tk_img = ImageTk.PhotoImage(img)
                    self.lbl_preview.config(image=self.tk_img, text="")
                    return
                except Exception as e:
                    self.lbl_preview.config(image="", text=f"Error loading embedded PNG: {e}")
                    return
            else:
                self.lbl_preview.config(image="", text="No embedded PNG available.")
                return

        if self.use_embedded_pngs.get():
            patched_png_path = os.path.join(self.patched_png_folder, base + ".png")
            if os.path.exists(patched_png_path):
                self.show_image(patched_png_path)
                return

            if psg_name in EMBEDDED_PNGS:
                try:
                    img = Image.open(io.BytesIO(b64decode(EMBEDDED_PNGS[psg_name])))
                    img = img.convert("RGB")
                    img.thumbnail((300, 300))
                    self.tk_img = ImageTk.PhotoImage(img)
                    self.lbl_preview.config(image=self.tk_img, text="")
                    return
                except Exception as e:
                    self.lbl_preview.config(image="", text=f"Error loading embedded PNG: {e}")
                    return
        else:
            if self.png_folder:
                png_path = os.path.join(self.png_folder, base + ".png")
                if os.path.exists(png_path):
                    self.show_image(png_path)
                    return

        self.lbl_preview.config(image="", text="PNG not found")

    def show_image(self, path):
        try:
            img = Image.open(path)
            img = img.convert("RGB")
            img.thumbnail((300, 300))
            self.tk_img = ImageTk.PhotoImage(img)
            self.lbl_preview.config(image=self.tk_img, text="")
        except Exception as e:
            self.lbl_preview.config(image="", text=f"Preview error: {e}")

    def apply_patch(self):
        if not self.dds_files:
            messagebox.showwarning("Missing DDS", "Select at least one DDS or PSG file.")
            return

        if not self.lst_psgs.curselection():
            messagebox.showwarning("Missing PSGs", "Select one or more PSG files.")
            return

        try:
            ext = os.path.splitext(self.dds_files[0])[1].lower()
            with open(self.dds_files[0], "rb") as f:
                if ext == ".dds":
                    f.seek(0x80)
                    dds_payload = f.read()
                    f.seek(0)
                    img_data = f.read()
                elif ext == ".psg":
                    f.seek(0x248)
                    dds_payload = f.read()
                    img_data = dds_payload
                else:
                    raise Exception("Unsupported file format")
        except Exception as e:
            messagebox.showerror("Source Read Error", str(e))
            return

        os.makedirs(self.patched_png_folder, exist_ok=True)

        for idx in self.lst_psgs.curselection():
            psg_name = self.matching_psgs[idx]
            psg_path = os.path.join(self.psg_folder, psg_name)
            base = os.path.splitext(psg_name)[0]
            meta = FIX_METADATA.get(psg_name)

            if not meta:
                self.log(f"No metadata for {psg_name}")
                continue

            try:
                header = bytes.fromhex(meta["header"])
                tail = bytes.fromhex(meta["tail"]) if meta["tail"] else b""

                if self.backup_enabled.get():
                    bak_path = psg_path + ".bak"
                    if not os.path.exists(bak_path):
                        with open(psg_path, "rb") as f:
                            original_data = f.read()
                        with open(bak_path, "wb") as bak:
                            bak.write(original_data)
                        self.log(f"Backup created: {os.path.basename(bak_path)}")

                with open(psg_path, "r+b") as f:
                    f.seek(0x240)
                    f.write(header)
                    f.seek(0x248)
                    f.write(dds_payload)
                    if tail:
                        f.write(tail)

                try:
                    img = Image.open(io.BytesIO(img_data)).convert("RGB")
                    patched_png_path = os.path.join(self.patched_png_folder, base + ".png")
                    img.save(patched_png_path)

                    if self.png_folder:
                        img.save(os.path.join(self.png_folder, base + ".png"))

                    self.log(f"{psg_name}: patched and PNG saved")
                except Exception as e:
                    self.log(f"{psg_name}: patched, but PNG preview failed: {e}")

            except Exception as e:
                self.log(f"Error patching {psg_name}: {e}")

        self.update_preview()

    def export_selected_tgas(self):
        if not self.lst_psgs.curselection():
            messagebox.showwarning("No Selection", "Select one or more PSG files to export.")
            return

        os.makedirs(self.exported_tga_folder, exist_ok=True)

        for idx in self.lst_psgs.curselection():
            psg_name = self.matching_psgs[idx]
            b64_data = EMBEDDED_TGA.get(psg_name)

            if not b64_data:
                self.log(f"No embedded TGA found for {psg_name}")
                continue

            try:
                tga_data = base64.b64decode(b64_data)
                out_path = os.path.join(
                    self.exported_tga_folder,
                    os.path.splitext(psg_name)[0] + ".tga"
                )
                with open(out_path, "wb") as f:
                    f.write(tga_data)
                self.log(f"Exported TGA: {os.path.basename(out_path)}")
            except Exception as e:
                self.log(f"Failed to export {psg_name}: {e}")


if __name__ == "__main__":
    root = tk.Tk()

    try:
        if getattr(sys, "frozen", False):
            icon_path = os.path.join(sys._MEIPASS, "your_icon.ico")
        else:
            icon_path = os.path.join(os.path.dirname(__file__), "your_icon.ico")
        root.iconbitmap(icon_path)
    except Exception as e:
        print("Icon load failed:", e)

    app = PSGEditorApp(root)
    root.geometry("950x720")
    root.mainloop()