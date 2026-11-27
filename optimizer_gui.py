"""Desktop interface for the FDM surface angle optimizer."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import trimesh
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from orientation_optimizer import optimize, metrics


def draw_mesh(ax, mesh, low, high, title):
    ax.clear()
    ax.set_title(title)
    if mesh is None:
        ax.set_axis_off()
        return
    ax.set_axis_on()
    d = mesh.face_normals[:, 2]
    bad = (d >= np.cos(np.deg2rad(high))) & (d <= np.cos(np.deg2rad(low)))
    light = np.clip(mesh.face_normals @ np.array([.3, -.4, .866]), -1, 1)
    shade = .72 + .23 * light
    colors = shade[:, None] * np.array([.40, .67, .80])[None, :]
    colors[bad] = [.90, .20, .17]
    ax.add_collection3d(Poly3DCollection(mesh.triangles, facecolors=colors, edgecolors='none'))
    center = mesh.bounds.mean(axis=0)
    span = max(mesh.extents) * .57
    ax.set_xlim(center[0]-span, center[0]+span)
    ax.set_ylim(center[1]-span, center[1]+span)
    ax.set_zlim(center[2]-span, center[2]+span)
    ax.set_box_aspect((1, 1, 1))
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z (up)')
    ax.view_init(elev=35, azim=-55)


class App:
    def __init__(self, root):
        self.root = root
        root.title('FDM Surface Angle Optimizer | v0.2')
        root.geometry('1160x760'); root.minsize(850, 600)
        self.mesh = self.output = self.report = self.source = None
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.status = tk.StringVar(value='Open an STL or try the built-in 10° test block.')
        self.summary = tk.StringVar(value='No model loaded.')
        controls = ttk.Frame(root, padding=12); controls.pack(fill='x')
        self.open_btn = ttk.Button(controls, text='Open STL', command=self.open_file); self.open_btn.grid(row=0,column=0,padx=4)
        self.demo_btn = ttk.Button(controls, text='Demo block', command=self.demo); self.demo_btn.grid(row=0,column=1,padx=4)
        self.run_btn = ttk.Button(controls, text='Optimize', command=self.run, state='disabled'); self.run_btn.grid(row=0,column=2,padx=4)
        self.save_btn = ttk.Button(controls, text='Export STL + report', command=self.save, state='disabled'); self.save_btn.grid(row=0,column=3,padx=4)
        self.fields = []
        for i,(label,value) in enumerate([('Min angle °','5'),('Max angle °','13'),('Margin °','0.5'),('Overhang °','45'),('Samples','2048')]):
            ttk.Label(controls,text=label).grid(row=1,column=i,pady=(12,2))
            entry=ttk.Entry(controls,width=13); entry.insert(0,value); entry.grid(row=2,column=i,padx=4); self.fields.append(entry)
        ttk.Label(root,textvariable=self.summary,padding=(14,5),wraplength=1050).pack(fill='x')
        ttk.Label(root,text='Red = upward-facing triangles in selected angle band. Blue = other faces. Drag to orbit; use toolbar to zoom/reset.',padding=(14,5),wraplength=1050).pack(fill='x')
        self.fig=Figure(figsize=(10,5),dpi=100,layout='constrained')
        self.axes=[self.fig.add_subplot(121,projection='3d'),self.fig.add_subplot(122,projection='3d')]
        self.canvas=FigureCanvasTkAgg(self.fig,master=root)
        self.canvas.get_tk_widget().pack(fill='both',expand=True)
        NavigationToolbar2Tk(self.canvas,root)
        ttk.Label(root,textvariable=self.status,padding=12,wraplength=1050).pack(fill='x')
        self.render(5,13)

    def settings(self):
        low,high,margin,overhang=map(float,[e.get() for e in self.fields[:4]])
        samples=int(self.fields[4].get())
        if not 0<low<high<90 or not 0<=margin<low or not 0<overhang<90 or not 32<=samples<=100000:
            raise ValueError('Require 0 < min < max < 90, 0 <= margin < min, 0 < overhang < 90, and 32–100000 samples.')
        return low,high,margin,overhang,samples

    def load(self, mesh, source=None):
        if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume<=0:
            raise ValueError('Use a watertight STL with consistent outward winding and positive volume.')
        low,high,margin,overhang,_=self.settings()
        self.mesh,self.source,self.output,self.report=mesh,source,None,None
        self.save_btn.config(state='disabled'); self.run_btn.config(state='normal')
        area=metrics(mesh.face_normals,mesh.area_faces,[[0,0,1]],low,high,margin,overhang)[0,0]
        self.summary.set(f'{source.name if source else "Demo block"} | {len(mesh.faces):,} triangles | Original undesirable area: {area:.3f} mm²')
        self.status.set('Ready. Click Optimize. Large meshes may take longer to render and search.')
        self.render(low,high)

    def open_file(self):
        path=filedialog.askopenfilename(filetypes=[('STL model','*.stl')])
        if path:
            try: self.load(trimesh.load(path,force='mesh'),Path(path))
            except Exception as e: messagebox.showerror('Cannot load STL',str(e))

    def demo(self):
        try:
            mesh=trimesh.creation.box(extents=[30,20,8])
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.deg2rad(10),[1,0,0]))
            self.load(mesh)
        except Exception as e: messagebox.showerror('Cannot load demo',str(e))

    def render(self,low,high):
        draw_mesh(self.axes[0],self.mesh,low,high,'Original orientation')
        draw_mesh(self.axes[1],self.output,low,high,'Optimized orientation')
        self.canvas.draw_idle()

    def busy(self,yes):
        for w in [self.open_btn,self.demo_btn,self.run_btn,*self.fields]: w.config(state='disabled' if yes else 'normal')
        self.save_btn.config(state='normal' if not yes and self.output is not None else 'disabled')

    def run(self):
        if self.mesh is None: return
        try: params=self.settings()
        except Exception as e: messagebox.showerror('Invalid settings',str(e)); return
        self.output=self.report=None
        self.busy(True); self.status.set('Searching candidate orientations…')
        future=self.pool.submit(optimize,self.mesh.copy(),*params)
        self.root.after(100,lambda:self.poll(future,params))

    def poll(self,future,params):
        if not future.done(): self.root.after(100,lambda:self.poll(future,params)); return
        try:
            self.output,self.report=future.result()
            a=self.report['before']['bad_area_mm2']; b=self.report['after']['bad_area_mm2']
            p=self.report['after']['downward_projection_proxy_mm2']
            self.summary.set(f'Undesirable area: {a:.3f} → {b:.3f} mm² | Downward overhang projection: {p:.3f} mm² (proxy only)')
            self.render(*params[:2]); self.status.set('Complete. Inspect orientation, supports, adhesion and strength in your slicer before printing.')
        except Exception as e:
            self.status.set('Optimization failed.'); messagebox.showerror('Optimization failed',str(e))
        finally: self.busy(False)

    def save(self):
        if self.output is None: return
        name=filedialog.asksaveasfilename(defaultextension='.stl',filetypes=[('STL model','*.stl')],initialfile=(self.source.stem if self.source else 'demo')+'_optimized.stl')
        if not name: return
        try:
            path=Path(name); sidecar=path.with_suffix('.json')
            if path.suffix.lower()!='.stl' or (self.source and path.resolve()==self.source.resolve()): raise ValueError('Choose a new STL filename, not the original input.')
            if sidecar.exists() and not messagebox.askyesno('Replace report?',f'Replace {sidecar.name}?'): return
            self.output.export(path)
            saved=trimesh.load(path,force='mesh'); low,high=self.report['angle_band_deg']
            report=dict(self.report,exported_watertight=bool(saved.is_watertight),exported_bad_area_mm2=float(metrics(saved.face_normals,saved.area_faces,[[0,0,1]],low,high,self.report['margin_deg'],self.report['overhang_angle_deg'])[0,0]))
            sidecar.write_text(json.dumps(report,indent=2)+'\n')
            self.status.set(f'Exported {path.name} and JSON report. Reimported mesh watertight: {saved.is_watertight}.')
        except Exception as e: messagebox.showerror('Export failed',str(e))


if __name__=='__main__':
    root=tk.Tk(); App(root); root.mainloop()
