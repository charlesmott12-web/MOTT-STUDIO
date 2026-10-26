"""Mott Studio 2.5 UI preview: multitrack DAW. MIT license."""
import json, os, time, uuid, queue, threading, math
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox, colorchooser
import numpy as np
from scipy import signal
import sounddevice as sd
import soundfile as sf

RATE=44100; BLOCK=512
BG='#0d1118'; PANEL='#1a2230'; FG='#edf3fa'; GOLD='#e6b56a'; BLUE='#48b4d4'; BORDER='#303d50'; MUTED='#8ea1b6'
class Studio:
 def __init__(self,root):
  self.root=root;root.title('Mott Studio 2.6 | Songwriting Workspace');root.geometry('1380x860');root.minsize(940,610);root.configure(bg=BG)
  self.project=None;self.tracks=[];self.clips=[];self.undo=[];self.selected=None;self.mode=tk.StringVar(value='Normal');self.device=tk.StringVar();self.output=tk.StringVar();self.devices=[];self.outputs=[]
  self.position=0.;self.zoom=85.;self.rowheight=88;self.running=False;self.stream=None;self.recorded=[];self.capture_start=0;self.playhead=0;self.meters={};self.events=queue.Queue();self.cache={};self.loop_start=tk.DoubleVar(value=0);self.loop_end=tk.DoubleVar(value=8);self.countin=tk.BooleanVar(value=False);self.metronome=tk.BooleanVar(value=False);self.bpm=tk.IntVar(value=120);self.tap_times=[];self.input_widgets={};self.active_inputs={};self.meter_levels={};self.meter_events=queue.Queue();self.meter_smoothed={};self.markers=[];self.lyrics='';self.drag=None;self.snap_enabled=tk.BooleanVar(value=True);self.grid_div=tk.StringVar(value='1/16');self.signature=tk.IntVar(value=4);self.master_gain=tk.DoubleVar(value=1.0);self.record_origin=0.;self.dock=tk.StringVar(value='Bottom');self.notes_visible=tk.BooleanVar(value=True)
  self.fx_filter_states={};self.fx_compressor_states={};self.show_grid=tk.BooleanVar(value=True);self.show_playhead=tk.BooleanVar(value=True);self.loop_playback=tk.BooleanVar(value=False);self.auto_smooth=tk.BooleanVar(value=True);self.monitor_stream=None;self.monitor_device=None;self.clip_peak={};self.ui_size=tk.StringVar(value='Compact');self.showmix=tk.BooleanVar(value=True);self.build();self.scan();root.after(80,self.tick);root.after(400,self.monitor_tick);root.protocol('WM_DELETE_WINDOW',self.close)
 def button(self,parent,label,command):return tk.Button(parent,text=label,command=command,bg='#29384a',fg=FG,activebackground='#415672',activeforeground='white',relief='flat',padx=6,pady=3,font=('Segoe UI Semibold',9),cursor='hand2',bd=0)
 def build(self):
  style=ttk.Style(self.root)
  try:style.theme_use('clam')
  except tk.TclError:pass
  style.configure('TCombobox',fieldbackground='#233044',background='#233044',foreground='#10151b',padding=5)
  style.configure('TScrollbar',background=PANEL,troughcolor=BG)
  menu=tk.Menu(self.root);f=tk.Menu(menu,tearoff=False)
  for label,fn in [('New project',self.new),('Open project',self.open),('Save',self.save),('Import WAV',self.import_wav),('Export stereo WAV',self.export),('Exit',self.close)]:f.add_command(label=label,command=fn)
  menu.add_cascade(label='File',menu=f);e=tk.Menu(menu,tearoff=False);e.add_command(label='Undo',command=self.undo_edit);e.add_command(label='Split clip at playhead',command=self.split);menu.add_cascade(label='Edit',menu=e);view=tk.Menu(menu,tearoff=False);view.add_checkbutton(label='Lyrics / Notes',variable=self.notes_visible,command=self.toggle_lyrics);view.add_checkbutton(label='Mix console',variable=self.showmix,command=self.toggle_mixer);view.add_checkbutton(label='Grid lines',variable=self.show_grid,command=self.draw);view.add_checkbutton(label='Playhead',variable=self.show_playhead,command=self.draw);view.add_separator();view.add_command(label='Recording layout',command=lambda:self.workspace('Recording'));view.add_command(label='Editing layout',command=lambda:self.workspace('Editing'));view.add_command(label='Mixing layout',command=lambda:self.workspace('Mixing'));menu.add_cascade(label='View',menu=view);self.root.config(menu=menu);self.root.bind('<Control-z>',lambda e:self.undo_edit());self.root.bind('<KeyPress-s>',lambda e:self.split() if not isinstance(e.widget,(tk.Entry,tk.Text,ttk.Combobox)) else None)
  top=tk.Frame(self.root,bg=BG);top.pack(fill='x',padx=10,pady=2)
  tk.Label(top,text='MOTT STUDIO',bg=BG,fg=FG,font=('Segoe UI Semibold',11)).pack(side='left');tk.Label(top,text='  •  2.6',bg=BG,fg=GOLD,font=('Segoe UI Semibold',10)).pack(side='left')
  self.status=tk.StringVar(value='Create or open a project to begin.');tk.Label(self.root,textvariable=self.status,bg=BG,fg='#b9c5ce',anchor='w').pack(fill='x',padx=16)
  controls=tk.Frame(self.root,bg=PANEL,highlightbackground=BORDER,highlightthickness=1);controls.pack(side='bottom',fill='x',padx=6,pady=3)
  for label,fn in [('● REC',self.record),('▶ PLAY',self.play),('■ STOP',self.stop),('|◀ START',self.return_start),('+ TRACK',self.add_track),('IMPORT',self.import_wav),('EXPORT',self.export),('BOUNCE',self.bounce)]:
   b=self.button(controls,label,fn);b.pack(side='left',padx=2,pady=3)
   if 'REC' in label:b.configure(bg='#a53e48',activebackground='#c8565e')
   elif 'PLAY' in label:b.configure(bg='#1c7869',activebackground='#2a9d82')
  tk.Checkbutton(controls,text='↻ LOOP',variable=self.loop_playback,bg=PANEL,fg=GOLD,selectcolor=BG,activebackground=PANEL).pack(side='left',padx=3)
  ttk.Combobox(controls,textvariable=self.mode,values=['Normal','Time selection','Punch','Loop takes'],width=11,state='readonly').pack(side='left',padx=3)
  tk.Checkbutton(controls,text='Click',variable=self.metronome,bg=PANEL,fg=FG,selectcolor=BG).pack(side='left')
  tk.Checkbutton(controls,text='Count-in',variable=self.countin,bg=PANEL,fg=FG,selectcolor=BG).pack(side='left')
  tk.Label(controls,text='BPM',bg=PANEL,fg=FG).pack(side='left',padx=(8,2));tk.Spinbox(controls,from_=30,to=300,textvariable=self.bpm,width=4).pack(side='left');self.button(controls,'TAP',self.tap_tempo).pack(side='left',padx=3);tk.Label(controls,text='Grid',bg=PANEL,fg=FG).pack(side='left');ttk.Combobox(controls,textvariable=self.grid_div,values=['1/1','1/2','1/4','1/8','1/16','1/32'],width=5,state='readonly').pack(side='left');tk.Checkbutton(controls,text='Snap',variable=self.snap_enabled,bg=PANEL,fg=FG,selectcolor=BG).pack(side='left');
  devices=tk.Frame(self.root,bg=BG);devices.pack(fill='x',padx=8,pady=1)
  tk.Label(devices,text='Input:',bg=BG,fg=FG).pack(side='left');self.indev=ttk.Combobox(devices,textvariable=self.device,width=23,state='readonly');self.indev.pack(side='left',padx=5)
  tk.Label(devices,text='Output:',bg=BG,fg=FG).pack(side='left');self.outdev=ttk.Combobox(devices,textvariable=self.output,width=23,state='readonly');self.outdev.pack(side='left',padx=5);self.button(devices,'Refresh',self.scan).pack(side='left');self.button(devices,'TUNER',self.tuner).pack(side='left',padx=5)
  bar=tk.Frame(self.root,bg=BG);bar.pack(fill='x',padx=8,pady=1)
  for label,var in [('From',self.loop_start),('To',self.loop_end)]:tk.Label(bar,text=label,bg=BG,fg=FG).pack(side='left');tk.Entry(bar,textvariable=var,width=7).pack(side='left',padx=6)
  self.clock=tk.StringVar(value='00:00.00');tk.Label(bar,textvariable=self.clock,bg=BG,fg=GOLD,font=('Consolas',12,'bold')).pack(side='right')
  self.mainpane=tk.PanedWindow(self.root,orient='vertical',bg=BORDER,sashwidth=7,sashrelief='flat');self.mainpane.pack(fill='both',expand=True,padx=12,pady=5)
  self.editorrow=tk.PanedWindow(self.mainpane,orient='horizontal',bg=BORDER,sashwidth=7)
  self.mainpane.add(self.editorrow,minsize=160,stretch='always')
  center=tk.Frame(self.editorrow,bg=BG);self.editorrow.add(center,minsize=350,stretch='always')
  self.canvas=tk.Canvas(center,bg='#111927',highlightthickness=1,highlightbackground=BORDER,cursor='crosshair');self.canvas.pack(fill='both',expand=True)
  self.lyricpanel=tk.Frame(self.editorrow,bg=PANEL);self.editorrow.add(self.lyricpanel,minsize=100)
  tk.Label(self.lyricpanel,text='SONG LYRICS / NOTES',bg=PANEL,fg=GOLD,font=('Segoe UI Semibold',11)).pack(anchor='w',padx=8,pady=5)
  self.lyrictext=tk.Text(self.lyricpanel,wrap='word',undo=True,bg='#172331',fg=FG,insertbackground=FG,font=('Segoe UI',11),relief='flat',width=28);self.lyrictext.pack(fill='both',expand=True,padx=7,pady=4)
  self.lyrictext.bind('<FocusOut>',lambda e:self.save())
  self.mixerpanel=tk.Frame(self.mainpane,bg=PANEL);self.mainpane.add(self.mixerpanel,minsize=95,height=250)

  self.canvas.bind('<Double-Button-1>',self.double_click);self.canvas.bind('<Button-1>',self.click);self.canvas.bind('<B1-Motion>',self.drag_motion);self.canvas.bind('<ButtonRelease-1>',self.drag_release);self.canvas.bind('<Button-3>',self.context);self.canvas.bind('<Control-MouseWheel>',self.zoom_wheel);self.canvas.bind('<Shift-MouseWheel>',self.height_wheel);self.canvas.bind('<MouseWheel>',self.scroll_wheel);self.canvas.bind('<Configure>',lambda e:self.draw())
  self.menu=tk.Menu(self.root,tearoff=0);self.marker_menu=tk.Menu(self.root,tearoff=0);self.marker_menu.add_command(label='Add marker here',command=self.add_marker);self.marker_menu.add_command(label='Edit nearest marker',command=self.edit_marker);self.marker_menu.add_command(label='Remove nearest marker',command=self.remove_marker);self.marker_menu.add_command(label='Change marker color',command=self.marker_color)
  for label,fn in [('Split at playhead',self.split),('Trim to selection',self.trim),('Move clip',self.move),('Copy clip',self.copy),('Clip gain',self.clip_gain),('Add volume automation point',self.add_automation_point),('Edit volume automation points',self.edit_automation_points),('Track FX',self.selected_track_fx),('Mute/unmute clip',self.clip_mute),('Delete clip',self.delete),('Header color',self.track_color),('Track background color',lambda:self.set_track_property_color('background_color')),('Clip color',lambda:self.set_track_property_color('clip_color')),('Waveform color',lambda:self.set_track_property_color('waveform_color')),('Rename track',self.rename_selected_track),('Set fade lengths',self.set_fades)]:self.menu.add_command(label=label,command=fn)
  mixhead=tk.Frame(self.mixerpanel,bg=BG);mixhead.pack(fill='x',padx=6);tk.Label(mixhead,text='MIX CONSOLE',bg=BG,fg=GOLD,font=('Segoe UI Semibold',11)).pack(side='left');tk.Checkbutton(mixhead,text='Show mixer',variable=self.showmix,command=self.draw_mixer,bg=BG,fg=FG,selectcolor=PANEL).pack(side='right')
  tk.Label(mixhead,text='Dock',bg=BG,fg=FG).pack(side='left',padx=(15,3));dock_selector=ttk.Combobox(mixhead,textvariable=self.dock,values=['Bottom','Top','Left','Right','Window'],width=8,state='readonly');dock_selector.pack(side='left');dock_selector.bind('<<ComboboxSelected>>',lambda e:self.set_dock())
  tk.Label(mixhead,text='MASTER',bg=BG,fg=GOLD).pack(side='left',padx=(10,3));tk.Scale(mixhead,from_=0,to=1.5,orient='horizontal',variable=self.master_gain,resolution=.01,length=92,showvalue=False,sliderlength=12,bg=BG,troughcolor='#101923',fg=FG,highlightthickness=0,bd=0).pack(side='left')
  self.mixer=tk.Frame(self.mixerpanel,bg=PANEL,height=190);self.mixer.pack(fill='both',expand=True,padx=4,pady=2);self.draw()
 def toggle_lyrics(self):
  if self.notes_visible.get():
   if str(self.lyricpanel) not in self.editorrow.panes():self.editorrow.add(self.lyricpanel,minsize=100)
  else:
   if str(self.lyricpanel) in self.editorrow.panes():self.editorrow.forget(self.lyricpanel)
 def toggle_mixer(self):
  if self.showmix.get():
   if str(self.mixerpanel) not in self.mainpane.panes():self.mainpane.add(self.mixerpanel,minsize=95)
   self.draw_mixer()
  else:
   if str(self.mixerpanel) in self.mainpane.panes():self.mainpane.forget(self.mixerpanel)
 def workspace(self,name):
  self.notes_visible.set(name=='Editing');self.showmix.set(name=='Mixing');self.toggle_lyrics();self.toggle_mixer()
  self.rowheight=72 if name=='Recording' else 100 if name=='Editing' else 68
  self.draw()
 def track_by_selection(self):
  if self.selected is not None:
   clip=self.selected_clip()
   if clip:return next((t for t in self.tracks if t['id']==clip['track']),None)
  return self.tracks[0] if self.tracks else None
 def set_track_property_color(self,key):
  t=self.track_by_selection()
  if not t:return
  color=colorchooser.askcolor(color=t.get(key,'#26798b'),title=key.replace('_',' ').title(),parent=self.root)[1]
  if color:t[key]=color;self.save();self.draw();self.draw_mixer()
 def rename_selected_track(self):
  t=self.track_by_selection()
  if not t:return
  name=simpledialog.askstring('Rename track','Track name:',initialvalue=t['name'],parent=self.root)
  if name and name.strip():t['name']=name.strip();self.save();self.draw();self.draw_mixer()
 def double_click(self,e):
  if e.x<235 and e.y>=58:
   row=int((e.y-58)//self.rowheight)
   if 0<=row<len(self.tracks):
    t=self.tracks[row];name=simpledialog.askstring('Rename track','Track name:',initialvalue=t['name'],parent=self.root)
    if name and name.strip():t['name']=name.strip();self.save();self.draw();self.draw_mixer()
 def stop_monitor(self):
  stream=self.monitor_stream;self.monitor_stream=None;self.monitor_device=None
  if stream is not None:
   try:stream.stop();stream.close()
   except Exception:pass
 def monitor_tick(self):
  try:
   if self.running:
    self.stop_monitor()
   else:
    inp=self.chosen(self.devices,self.device.get())
    armed={t['id']:max(0,int(t.get('input',1))-1) for t in self.tracks if t.get('arm')}
    wanted=(inp[1],max(armed.values(),default=0)+1) if inp and armed else None
    if wanted!=self.monitor_device:self.stop_monitor()
    if wanted and self.monitor_stream is None:
     channels=min(inp[2],wanted[1]);identities=dict(armed)
     if channels>0 and max(identities.values())<channels:
      def cb(indata,frames,timing,status):
       levels={tid:float(np.sqrt(np.mean(indata[:,ch].astype(np.float64)**2))) for tid,ch in identities.items() if ch<indata.shape[1]}
       try:self.meter_events.put_nowait(levels)
       except Exception:pass
      try:
       self.monitor_stream=sd.InputStream(device=inp[1],samplerate=RATE,blocksize=1024,channels=channels,callback=cb)
       self.monitor_stream.start();self.monitor_device=wanted
      except Exception:
       self.stop_monitor()
  except Exception:pass
  self.root.after(700,self.monitor_tick)
 def scan(self):
  try:
   all_d=sd.query_devices();self.devices=[(f'{i}: {d["name"]}',i,int(d['max_input_channels'])) for i,d in enumerate(all_d) if d['max_input_channels']>0];self.outputs=[(f'{i}: {d["name"]}',i,int(d['max_output_channels'])) for i,d in enumerate(all_d) if d['max_output_channels']>0]
   self.indev['values']=[x[0] for x in self.devices];self.outdev['values']=[x[0] for x in self.outputs]
   if self.devices:self.device.set(next((x[0] for x in self.devices if 'irig' in x[0].lower()),self.devices[0][0]))
   if self.outputs:self.output.set(next((x[0] for x in self.outputs if 'irig' in x[0].lower()),self.outputs[0][0]))
   self.refresh_track_inputs()
  except Exception as exc:self.status.set(str(exc))
 def chosen(self,items,value):return next((x for x in items if x[0]==value),None)
 def tap_tempo(self):
  now=time.monotonic();self.tap_times=[t for t in self.tap_times if now-t<3.0];self.tap_times.append(now)
  if len(self.tap_times)>1:
   gaps=[b-a for a,b in zip(self.tap_times,self.tap_times[1:])];self.bpm.set(max(30,min(300,round(60/(sum(gaps)/len(gaps))))))
  self.status.set(f'Tap tempo: {self.bpm.get()} BPM')
 def set_input(self,track,value):
  try:track['input']=int(value.split(' ')[0]);self.save()
  except (ValueError,IndexError):pass
 def refresh_track_inputs(self):
  for tid,combo in getattr(self,'input_widgets',{}).items():
   try:combo['values']=['1 - Input 1','2 - Input 2']
   except tk.TclError:pass
 def new(self):
  folder=filedialog.askdirectory(title='Choose parent folder');name=simpledialog.askstring('Project','Song name:') if folder else None
  if not name:return
  self.project=Path(folder)/''.join(c if c.isalnum() or c in ' -_' else '_' for c in name);self.project.mkdir(parents=True,exist_ok=True);(self.project/'audio').mkdir(exist_ok=True);self.tracks=[];self.clips=[];self.markers=[];self.lyrics='';self.lyrictext.delete('1.0','end');self.position=0;self.add_track('Track 1');self.save()
 def open(self):
  folder=filedialog.askdirectory(title='Open Mott Studio project');
  if not folder:return
  try:
   self.project=Path(folder);obj=json.loads((self.project/'project.json').read_text());self.tracks=obj.get('tracks',[]);self.clips=obj.get('clips',[]);self.markers=obj.get('markers',[]);self.lyrics=obj.get('lyrics','');self.lyrictext.delete('1.0','end');self.lyrictext.insert('1.0',self.lyrics);self.bpm.set(obj.get('bpm',120));self.signature.set(obj.get('signature',4));self.master_gain.set(obj.get('master_gain',1.0));self.auto_smooth.set(obj.get('auto_smooth',True))
   if not self.tracks:
    old=self.clips;self.clips=[]
    for i,c in enumerate(old):self.add_track(c.get('name',f'Track {i+1}'));c['track']=self.tracks[-1]['id'];self.clips.append(c)
   self.cache.clear();self.draw();self.draw_mixer();self.status.set(f'Opened {folder}')
  except Exception as exc:messagebox.showerror('Open failed',str(exc))
 def save(self):
  if not self.project:return
  data={'format':'mott-studio-2.4','sample_rate':RATE,'tracks':self.tracks,'clips':self.clips,'markers':self.markers,'lyrics':self.lyrictext.get('1.0','end-1c') if hasattr(self,'lyrictext') else self.lyrics,'bpm':self.bpm.get(),'signature':self.signature.get(),'master_gain':self.master_gain.get(),'auto_smooth':self.auto_smooth.get()};tmp=self.project/'project.tmp';tmp.write_text(json.dumps(data,indent=2));os.replace(tmp,self.project/'project.json');self.status.set('Project saved: '+str(self.project))
 def add_track(self,name=None):
  if not self.project:
   create=messagebox.askyesno('Project required', 'Tracks need a project to save into.\n\nCreate a new project now?\n\nChoose No to cancel and open an existing project from File > Open project.')
   if create:
    self.new()  # New project creates Track 1 automatically.
   return
  if not isinstance(name,str):name=f'Track {len(self.tracks)+1}'
  self.snapshot()
  self.tracks.append({'id':uuid.uuid4().hex,'name':name,'input':min(len(self.tracks)+1,2),'arm':True,'mute':False,'solo':False,'gain':1.,'pan':0.,'color':'#26798b','fx':{}});self.draw();self.draw_mixer();self.save()
 def snapshot(self):self.undo.append(json.loads(json.dumps((self.tracks,self.clips))));self.undo=self.undo[-30:]
 def undo_edit(self):
  if self.undo:self.tracks,self.clips=self.undo.pop();self.draw();self.draw_mixer();self.save()
 def audio(self,filename):
  if filename not in self.cache:
   a,r=sf.read(self.project/'audio'/filename,always_2d=True,dtype='float32')
   if r!=RATE:raise ValueError(f'{filename}: sample rate must be 44100 Hz')
   self.cache[filename]=a
  return self.cache[filename]
 def process_fx(self,track,data):
  """Process a short stereo block, preserving filter and compressor state across blocks."""
  fx=track.get('fx',{});tid=track['id']
  if not fx or not any(v.get('enabled') for v in fx.values()):return data
  output=data.copy()
  eq=fx.get('EQ',{})
  if eq.get('enabled'):
   low=float(eq.get('low',0));mid=float(eq.get('mid',0));high=float(eq.get('high',0))
   # Three cascaded bell/shelf approximations; explicit state for seamless streaming.
   bands=[('low',180,low),('mid',1250,mid),('high',5000,high)]
   for name,frequency,db in bands:
    if abs(db)<.05:continue
    b,a=self.peaking_filter(frequency,db,0.75)
    key=(tid,name,round(db,2))
    zi=self.fx_filter_states.get(key)
    if zi is None:zi=np.zeros((2,2))
    for ch in range(2):output[:,ch],zi[ch]=signal.lfilter(b,a,output[:,ch],zi=zi[ch])
    self.fx_filter_states[key]=zi
  gate=fx.get('Gate',{})
  if gate.get('enabled'):
   threshold=10**(float(gate.get('threshold',-48))/20)
   rms=np.sqrt(np.mean(output*output,axis=1,keepdims=True))
   output*=np.clip(rms/(threshold+1e-9),0,1)**2
  comp=fx.get('Compressor',{})
  if comp.get('enabled'):
   threshold=float(comp.get('threshold',-18));ratio=max(1.,float(comp.get('ratio',3)))
   attack=max(.001,float(comp.get('attack',10))/1000);release=max(.005,float(comp.get('release',120))/1000)
   makeup=10**(float(comp.get('makeup',0))/20)
   env=self.fx_compressor_states.get(tid,0.)
   gains=np.empty(len(output),dtype=np.float32)
   alpha_attack=math.exp(-1/(RATE*attack));alpha_release=math.exp(-1/(RATE*release))
   for i,peak in enumerate(np.max(np.abs(output),axis=1)):
    alpha=alpha_attack if peak>env else alpha_release;env=alpha*env+(1-alpha)*float(peak)
    level_db=20*math.log10(max(env,1e-8));reduction=max(0.,level_db-threshold)*(1-1/ratio)
    gains[i]=10**(-reduction/20)*makeup
   self.fx_compressor_states[tid]=env;output*=gains[:,None]
  sat=fx.get('Saturation',{})
  if sat.get('enabled'):
   drive=max(1.,float(sat.get('drive',2)));mix=max(0.,min(1.,float(sat.get('mix',.35))))
   output=(1-mix)*output+mix*np.tanh(output*drive)/np.tanh(drive)
  limit=fx.get('Limiter',{})
  if limit.get('enabled'):
   ceiling=10**(float(limit.get('ceiling',-1))/20)
   output=np.clip(output,-ceiling,ceiling)
  return output
 def peaking_filter(self,freq,db,q):
  a=10**(db/40);w=2*math.pi*freq/RATE;alpha=math.sin(w)/(2*q)
  b=np.array([1+alpha*a,-2*math.cos(w),1-alpha*a]);d=np.array([1+alpha/a,-2*math.cos(w),1-alpha/a])
  return b/d[0],d/d[0]
 def mix_block(self,start,n):
  out=np.zeros((n,2),dtype=np.float32);solos=any(t['solo'] for t in self.tracks)
  for t in self.tracks:
   if t['mute'] or (solos and not t['solo']):continue
   track_audio=np.zeros((n,2),dtype=np.float32)
   for c in self.clips:
    if c.get('track')!=t['id'] or c.get('mute'):continue
    cs=round(c['start']*RATE);ce=cs+round(c['duration']*RATE);a=max(start,cs);b=min(start+n,ce)
    if b<=a:continue
    wave=self.audio(c['file']);ch=min(c.get('channel',0),wave.shape[1]-1)
    positions=np.arange(a-cs,b-cs,dtype=np.int64)
    base=round(c.get('offset',0)*RATE)
    if c.get('repeat'):
     period=max(1,round(c.get('loop_length',c['duration'])*RATE))
     indices=base+(positions%period)
    else:indices=base+positions
    indices=indices[indices<len(wave)]
    segment=wave[indices,ch]
    if not len(segment):continue
    gain=c.get('gain',1)*t['gain'];pan=t['pan'];local=np.arange(a-cs,a-cs+len(segment),dtype=np.float32)/RATE
    fade_in=max(0.,float(c.get('fade_in',0)));fade_out=max(0.,float(c.get('fade_out',0)))
    envelope=np.ones(len(segment),dtype=np.float32)
    if fade_in>0:envelope=np.minimum(envelope,np.clip(local/fade_in,0,1))
    if fade_out>0:envelope=np.minimum(envelope,np.clip((c['duration']-local)/fade_out,0,1))
    if c.get('repeat') and self.auto_smooth.get():
     period=max(.001,c.get('loop_length',c['duration']))
     phase=np.mod(local,period)
     smoothing=min(.004,period*.1)
     envelope*=np.minimum(1,np.minimum(phase/smoothing,(period-phase)/smoothing))
    points=sorted((float(x),float(g)) for x,g in c.get('automation',[]))
    if points:
     times=np.array([0.]+[max(0.,min(c['duration'],x)) for x,g in points]+[c['duration']]);values=np.array([1.]+[g for x,g in points]+[points[-1][1]])
     envelope*=np.interp(local,times,values).astype(np.float32)
    if c.get('stereo') and wave.shape[1]>=2:
     stereo=wave[indices[:len(segment)],:2]*envelope[:,None]*gain
     track_audio[a-start:a-start+len(segment),0]+=stereo[:,0]*min(1,1-pan)
     track_audio[a-start:a-start+len(segment),1]+=stereo[:,1]*min(1,1+pan)
    else:
     segment=segment*envelope
     track_audio[a-start:a-start+len(segment),0]+=segment*gain*min(1,1-pan)
     track_audio[a-start:a-start+len(segment),1]+=segment*gain*min(1,1+pan)
   out+=self.process_fx(t,track_audio)
  return out*self.master_gain.get()
 def total(self):return max([c['start']+c['duration'] for c in self.clips]+[0])
 def play(self):self.start(False)
 def record(self):self.start(True)
 def start(self,record):
  if self.running:return
  if not self.project:messagebox.showinfo('Project','Create a project first');return
  self.stop_monitor()
  inp=self.chosen(self.devices,self.device.get());out=self.chosen(self.outputs,self.output.get());armed=[t for t in self.tracks if t['arm']] if record else []
  if record and (not inp or not armed):messagebox.showerror('Input','Select input and arm at least one track');return
  if not out:messagebox.showerror('Output','Select an output device');return
  # PortAudio enumerates input and output endpoints separately on Windows.
  # Different device indices do NOT imply different physical interfaces.
  # Validate the actual channel counts and ask PortAudio to validate the pair.
  requested=max((int(t.get('input',1)) for t in armed),default=1)
  if record and (requested<1 or requested>inp[2]):
   messagebox.showerror('Input routing',f'Armed tracks require input {requested}, but {inp[0]} exposes {inp[2]} input channel(s).');return
  if out[2]<1:messagebox.showerror('Output routing','Selected output has no output channels.');return
  try:
   if record:
    sd.check_input_settings(device=inp[1],channels=requested,samplerate=RATE)
   sd.check_output_settings(device=out[1],channels=min(2,out[2]),samplerate=RATE)
  except Exception as exc:
   messagebox.showerror('Audio device settings',f'Unable to use the selected devices at {RATE} Hz.\\n{exc}');return
  self.recorded=[];self.record_origin=self.position;self.capture_start=int(self.position*RATE);self.playhead=self.capture_start;self.is_record=record;self.armed=armed;self.in_channels=requested if record else 1;self.running=True;self.active_inputs={t['id']:int(t.get('input',1))-1 for t in armed};self.record_bpm=max(30,min(300,int(self.bpm.get())));self.record_mode=self.mode.get();self.click_enabled=self.metronome.get()
  try:
   def callback(indata,outdata,frames,timing,status):
    if status:self.events.put(str(status))
    try:
     start=self.playhead;mix=self.mix_block(start,frames)
     if self.click_enabled:
      beat_samples=RATE*60/self.record_bpm
      for j in range(frames):
       phase=(start+j)%beat_samples
       if phase<round(RATE*.018):
        tick=(0.16 if int((start+j)/beat_samples)%4==0 else 0.09)*math.exp(-phase/(RATE*.004))*math.sin(2*math.pi*(1350 if int((start+j)/beat_samples)%4==0 else 900)*phase/RATE)
        mix[j,:]+=tick
     outdata[:]=np.clip(mix[:,:outdata.shape[1]],-1,1)
     try:
      levels={}
      for track in self.tracks:
       if self.is_record and track['id'] in self.active_inputs:
        ch=self.active_inputs[track['id']]
        if ch<indata.shape[1]:levels[track['id']]=float(np.sqrt(np.mean(indata[:,ch].astype(np.float64)**2)))
       elif not self.is_record:
        levels[track['id']]=float(np.sqrt(np.mean(mix.astype(np.float64)**2)))
      self.meter_events.put_nowait(levels)
     except Exception:pass
     if self.is_record:self.recorded.append(indata.copy())
     self.playhead+=frames
     if not self.is_record and self.loop_playback.get() and self.loop_end.get()>self.loop_start.get():
      if self.playhead>=int(self.loop_end.get()*RATE):self.playhead=int(self.loop_start.get()*RATE)
      elif not self.is_record and self.playhead>=int(self.total()*RATE):raise sd.CallbackStop
     if self.is_record and self.record_mode in ('Punch','Time selection') and self.playhead>=int(self.loop_end.get()*RATE):raise sd.CallbackStop
     if self.is_record and self.record_mode=='Loop takes' and self.playhead>=int(self.loop_end.get()*RATE):raise sd.CallbackStop
    except sd.CallbackStop:raise
    except Exception as exc:self.events.put('Audio callback error: '+str(exc));outdata.fill(0);raise sd.CallbackStop
   if record:
    self.stream=sd.Stream(device=(inp[1],out[1]),samplerate=RATE,blocksize=BLOCK,channels=(self.in_channels,min(2,out[2])),callback=callback,finished_callback=lambda:self.events.put('finished'))
   else:
    def output_callback(outdata,frames,timing,status):
     callback(np.zeros((frames,1),dtype=np.float32),outdata,frames,timing,status)
    self.stream=sd.OutputStream(device=out[1],samplerate=RATE,blocksize=BLOCK,channels=min(2,out[2]),callback=output_callback,finished_callback=lambda:self.events.put('finished'))
   self.stream.start();self.status.set('RECORDING' if record else 'PLAYING')
  except Exception as exc:self.running=False;self.stream=None;messagebox.showerror('Audio start failed',str(exc))
 def stop(self):
  if not self.running:return
  self.running=False
  if self.stream:
   try:self.stream.stop();self.stream.close()
   except Exception:pass
   self.stream=None
  if self.is_record and self.recorded:
   try:
    a=np.concatenate(self.recorded);filename='take_'+uuid.uuid4().hex[:12]+'.wav';sf.write(self.project/'audio'/filename,a,RATE,subtype='PCM_24');self.snapshot()
    for t in self.armed:
     ch=self.active_inputs[t['id']]
     if ch>=a.shape[1]:continue
     start=self.capture_start/RATE;duration=len(a)/RATE
     if self.mode.get() in ('Punch','Time selection'):
      lo=self.loop_start.get();hi=self.loop_end.get();skip=max(0,lo-start);start=max(start,lo);duration=max(0,min(start+duration,hi)-start);offset=skip
     else:offset=0
     if duration>0:self.clips.append({'track':t['id'],'file':filename,'channel':ch,'start':start,'offset':offset,'duration':duration,'gain':1.,'mute':False,'take':self.mode.get()})
    self.save();self.status.set(f'Recorded {len(a)/RATE:.1f}s on {len(self.armed)} armed track(s).')
   except Exception as exc:messagebox.showerror('Save recording failed',str(exc))
  if self.is_record:self.position=self.record_origin
  self.draw()
 def import_wav(self):
  if not self.project:return
  fn=filedialog.askopenfilename(filetypes=[('WAV audio','*.wav')]);
  if not fn:return
  try:
   a,r=sf.read(fn,always_2d=True,dtype='float32')
   if r!=RATE:messagebox.showerror('Sample rate','Import currently requires 44,100 Hz WAV.');return
   import shutil
   name='import_'+uuid.uuid4().hex[:8]+'.wav';shutil.copy2(fn,self.project/'audio'/name);self.add_track(Path(fn).stem);self.snapshot();self.clips.append({'track':self.tracks[-1]['id'],'file':name,'channel':0,'start':self.position,'offset':0,'duration':len(a)/RATE,'gain':1.,'mute':False});self.save();self.draw()
  except Exception as exc:messagebox.showerror('Import failed',str(exc))
 def export(self):
  if not self.project or not self.clips:return
  fn=filedialog.asksaveasfilename(defaultextension='.wav',filetypes=[('WAV','*.wav')]);
  if not fn:return
  try:
   with sf.SoundFile(fn,'w',samplerate=RATE,channels=2,subtype='PCM_24') as f:
    for start in range(0,int(self.total()*RATE),RATE*5):f.write(np.clip(self.mix_block(start,min(RATE*5,int(self.total()*RATE)-start)),-1,1))
   self.status.set('Exported '+fn)
  except Exception as exc:messagebox.showerror('Export failed',str(exc))
 def bounce(self):
  if not self.project or not self.clips:
   messagebox.showinfo('Bounce','Open a project with clips first');return
  if self.running:messagebox.showwarning('Bounce','Stop playback or recording first');return
  try:
   frames=int(self.total()*RATE);name='bounce_'+uuid.uuid4().hex[:8]+'.wav'
   with sf.SoundFile(self.project/'audio'/name,'w',samplerate=RATE,channels=2,subtype='PCM_24') as f:
    for i in range(0,frames,RATE*2):f.write(np.clip(self.mix_block(i,min(RATE*2,frames-i)),-1,1))
   self.add_track('Mixdown');track=self.tracks[-1];track['arm']=False
   self.clips.append({'track':track['id'],'file':name,'channel':0,'start':0.,'offset':0.,'duration':frames/RATE,'gain':1.,'mute':False,'stereo':True})
   self.cache.clear();self.save();self.draw();self.draw_mixer()
   messagebox.showinfo('Mixdown created','Added Mixdown track. Mute the source tracks while listening to the bounce to avoid doubling the audio.')
  except Exception as exc:messagebox.showerror('Bounce failed',str(exc))
 def selected_track_fx(self):
  c=self.selected_clip()
  if not c:return
  track=next((t for t in self.tracks if t['id']==c['track']),None)
  if track:self.open_fx(track)
 def open_fx(self,track):
  presets={'EQ':{'enabled':False,'low':0.,'mid':0.,'high':0.},'Compressor':{'enabled':False,'threshold':-18.,'ratio':3.,'attack':10.,'release':120.,'makeup':0.},'Gate':{'enabled':False,'threshold':-48.},'Saturation':{'enabled':False,'drive':2.,'mix':.35},'Limiter':{'enabled':False,'ceiling':-1.}}
  fx=track.setdefault('fx',{})
  window=tk.Toplevel(self.root);window.title('Mott FX | '+track['name']);window.configure(bg=PANEL);window.geometry('530x630')
  tk.Label(window,text='MOTT FX • '+track['name'],bg=PANEL,fg=GOLD,font=('Segoe UI Semibold',15)).pack(pady=(10,5))
  body=tk.Frame(window,bg=PANEL);body.pack(fill='both',expand=True)
  graph=tk.Canvas(body,height=145,bg='#111927',highlightthickness=0)
  graph.pack(fill='x',padx=12,pady=3)
  def paint_eq():
   graph.delete('all');ww=max(350,graph.winfo_width());hh=145
   for n in range(7):
    y=12+n*20;graph.create_line(12,y,ww-12,y,fill='#304254')
   for n,text in enumerate(('180 Hz','1.25 kHz','5 kHz')):
    x=45+n*(ww-90)/2;graph.create_text(x,135,text=text,fill=MUTED,font=('Segoe UI',8))
   pts=[];eq=fx.setdefault('EQ',dict(presets['EQ']))
   for n,key in enumerate(('low','mid','high')):
    x=45+n*(ww-90)/2;y=72-float(eq.get(key,0))*3.1;pts.append((x,y,key))
   graph.create_line(12,72,ww-12,72,fill='#4b6173')
   graph.create_line([v for x,y,k in pts for v in (x,y)],fill='#6bdcc1',width=3,smooth=True)
   for x,y,k in pts:graph.create_oval(x-7,y-7,x+7,y+7,fill=GOLD,outline='white',tags=('eqpoint',k))
  def drag_eq(e):
   n=max(0,min(2,round((e.x-45)/max(1,(graph.winfo_width()-90)/2))))
   key=('low','mid','high')[n];fx.setdefault('EQ',dict(presets['EQ']))[key]=round(max(-18,min(18,(72-e.y)/3.1)),1)
   refresh();paint_eq()
  graph.bind('<B1-Motion>',drag_eq);graph.bind('<Button-1>',drag_eq);graph.bind('<Configure>',lambda e:paint_eq())
  labels={'low':'Low (dB)','mid':'Mid (dB)','high':'High (dB)','threshold':'Threshold (dB)','ratio':'Ratio','attack':'Attack (ms)','release':'Release (ms)','makeup':'Makeup (dB)','drive':'Drive','mix':'Mix','ceiling':'Ceiling (dB)'}
  ranges={'low':(-18,18),'mid':(-18,18),'high':(-18,18),'threshold':(-60,0),'ratio':(1,12),'attack':(1,100),'release':(10,500),'makeup':(0,18),'drive':(1,12),'mix':(0,1),'ceiling':(-12,0)}
  def refresh():
   self.fx_filter_states.clear();self.fx_compressor_states.pop(track['id'],None);self.save()
  for name,defaults in presets.items():
   settings=fx.setdefault(name,dict(defaults))
   section=tk.LabelFrame(body,text=name,bg=PANEL,fg=FG,font=('Segoe UI Semibold',10),bd=1)
   section.pack(fill='x',padx=12,pady=3)
   enabled=tk.BooleanVar(value=settings.get('enabled',False))
   tk.Checkbutton(section,text='Enabled',variable=enabled,bg=PANEL,fg=FG,selectcolor=BG,command=lambda ss=settings,var=enabled:(ss.update(enabled=var.get()),refresh())).pack(side='left',padx=5)
   for key,value in defaults.items():
    if key=='enabled':continue
    var=tk.DoubleVar(value=settings.get(key,value));lo,hi=ranges[key]
    column=tk.Frame(section,bg=PANEL);column.pack(side='left',padx=4)
    tk.Label(column,text=labels.get(key,key),bg=PANEL,fg=MUTED,font=('Segoe UI',8)).pack()
    spin=tk.Scale(column,from_=hi,to=lo,resolution=.1,variable=var,orient='vertical',length=87,sliderlength=12,width=8,bg=PANEL,fg=FG,highlightthickness=0,troughcolor='#0d1521',font=('Segoe UI',8),command=lambda value,ss=settings,k=key:(ss.__setitem__(k,float(value)),refresh()))
    spin.pack(pady=(0,3))
    def apply(event=None,ss=settings,k=key,v=var,lower=lo,upper=hi):
     try:ss[k]=max(lower,min(upper,float(v.get())));refresh()
     except (tk.TclError,ValueError):pass
    spin.bind('<Return>',apply);spin.bind('<FocusOut>',apply)
  tk.Label(window,text='Built-in processing • EQ, compressor, gate, saturation & limiter',bg=PANEL,fg=MUTED,font=('Segoe UI',9)).pack(pady=7)
  self.button(window,'Save FX settings',lambda:(refresh(),window.destroy())).pack(pady=(1,10))
 def add_automation_point(self):
  c=self.selected_clip()
  if not c:return
  at=max(0.,min(c['duration'],self.position-c['start']))
  val=simpledialog.askfloat('Volume automation','Level at playhead (0.0 silence, 1.0 normal, 2.0 double):',initialvalue=1.,minvalue=0.,maxvalue=2.,parent=self.root)
  if val is None:return
  def change(clip):
   points=[p for p in clip.get('automation',[]) if abs(float(p[0])-at)>.01];points.append([at,val]);clip['automation']=sorted(points)
  self.edit(change)
 def edit_automation_points(self):
  c=self.selected_clip()
  if not c:return
  points=c.get('automation',[])
  response=simpledialog.askstring('Automation points','Enter time:gain pairs in seconds, separated by commas. Example: 0:1, 2:0.5, 3:1',initialvalue=', '.join(f'{x:g}:{y:g}' for x,y in points),parent=self.root)
  if response is None:return
  try:
   parsed=[]
   for part in response.split(','):
    if not part.strip():continue
    x,g=map(float,part.split(':'));assert 0<=x<=c['duration'] and 0<=g<=2
    parsed.append([x,g])
   self.edit(lambda cl:cl.update(automation=sorted(parsed)))
  except Exception:messagebox.showerror('Automation','Use pairs like 0:1, 2:0.5, 3:1. Times must fall inside the clip.')
 def tuner(self):
  if self.running:
   messagebox.showinfo('Tuner','Stop recording/playback before opening the tuner.');return
  inp=self.chosen(self.devices,self.device.get())
  if not inp:messagebox.showerror('Tuner','Choose a valid audio input first.');return
  window=tk.Toplevel(self.root);window.title('Mott Studio • Guitar Tuner');window.configure(bg=PANEL);window.geometry('380x220')
  note=tk.StringVar(value='Listening…');tk.Label(window,textvariable=note,font=('Segoe UI Semibold',29),bg=PANEL,fg=FG).pack(pady=13)
  cents_label=tk.StringVar(value='Pluck one string');tk.Label(window,textvariable=cents_label,font=('Segoe UI',13),bg=PANEL,fg=GOLD).pack()
  channel=tk.IntVar(value=1);tk.Label(window,text='Input channel',bg=PANEL,fg=FG).pack();ttk.Combobox(window,textvariable=channel,values=list(range(1,max(2,inp[2])+1)),width=6,state='readonly').pack()
  stopped=threading.Event();samples=queue.Queue(maxsize=3)
  def callback(indata,frames,timing,status):
   try:
    if not samples.full():samples.put_nowait(indata[:,max(0,min(indata.shape[1]-1,channel.get()-1))].copy())
   except Exception:pass
  try:
   stream=sd.InputStream(device=inp[1],channels=max(1,inp[2]),samplerate=RATE,blocksize=4096,callback=callback);stream.start()
  except Exception as exc:window.destroy();messagebox.showerror('Tuner',str(exc));return
  def update():
   if stopped.is_set() or not window.winfo_exists():return
   try:
    while samples.qsize()>1:samples.get_nowait()
    data=samples.get_nowait();data=data-np.mean(data)
    if np.max(np.abs(data))>.012:
     # normalized autocorrelation (sufficient for a simple monophonic tuner)
     lo,hi=int(RATE/1100),int(RATE/65)
     corr=np.correlate(data,data,mode='full')[len(data)-1:];corr[:lo]=0
     lag=lo+int(np.argmax(corr[lo:hi]));freq=RATE/lag
     midi=round(69+12*math.log2(freq/440));names=['C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B']
     note.set(f'{names[midi%12]}{midi//12-1}');cents=1200*math.log2(freq/(440*2**((midi-69)/12)))
     cents_label.set(f'{cents:+.0f} cents • '+('IN TUNE' if abs(cents)<5 else 'SHARP' if cents>0 else 'FLAT'))
   except queue.Empty:pass
   except Exception:pass
   window.after(120,update)
  def close_tuner():
   stopped.set()
   try:stream.stop();stream.close()
   except Exception:pass
   window.destroy()
  window.protocol('WM_DELETE_WINDOW',close_tuner);update()
 def draw(self):
  if not hasattr(self,'canvas'):return
  c=self.canvas;c.delete('all');w=max(c.winfo_width(),100);left=235;end=max(0,(w-left)/self.zoom)
  beat=60/max(30,self.bpm.get());measure=beat*max(1,self.signature.get());step=beat*4/int(self.grid_div.get().split('/')[1]);height=max(100,len(self.tracks)*self.rowheight+58);header=58
  c.create_rectangle(left,0,w,31,fill='#243142',outline='')
  c.create_rectangle(left,31,w,header,fill='#1b2837',outline='')
  for idx in range(min(1500,int(end/max(step,.002))+2)):
   sec=idx*step;x=left+sec*self.zoom
   if x>w:break
   isbar=abs(sec/measure-round(sec/measure))<.0001;isbeat=abs(sec/beat-round(sec/beat))<.0001
   pass # grid rendered above waveforms
   if isbar:pass # bar labels rendered last
  for m in self.markers:
   x=left+m['time']*self.zoom
   if left<=x<=w:
    c.create_line(x,header,x,height,fill=m.get('color',GOLD),dash=(4,4));c.create_text(x+3,14,text=m['name'][:24],anchor='nw',fill=m.get('color',GOLD),font=('Segoe UI',8,'bold'))
  for i,t in enumerate(self.tracks):
   y=58+i*self.rowheight;c.create_rectangle(0,y,left,y+self.rowheight-2,fill=t.get('color','#1f2b3a'),outline=BORDER);c.create_text(12,y+20,text=t['name'],fill=FG,anchor='w',font=('Segoe UI',11,'bold'))
   for j,(label,key,color) in enumerate([('R','arm','#e84d4d'),('M','mute','#43b86a'),('S','solo','#f0c64d')]):
    x=12+j*26
    if key=='arm':c.create_rectangle(x,y+35,x+21,y+56,fill=color if t[key] else '#46515d',outline='#f4a3a3' if t[key] else '#65717b',width=1)
    else:c.create_rectangle(x,y+35,x+21,y+56,fill=color if t[key] else '#46515d',outline='')
    c.create_text(x+11,y+46,text=label,fill='#11171c' if t[key] else FG,font=('Segoe UI',9,'bold'))
   c.create_text(150,y+46,text=f'IN {t.get("input",1)}',fill=GOLD,font=('Segoe UI',9,'bold'))
   level=self.meter_levels.get(t['id'],0.)
   fraction=max(0.,min(1.,(20*math.log10(max(level,1e-6))+48)/48))
   c.create_rectangle(142,y+52,222,y+59,fill='#273c48',outline='#485665')
   c.create_rectangle(142,y+52,142+80*fraction,y+59,fill='#5ad5aa',outline='')
   c.create_rectangle(left,y,w,y+self.rowheight-2,fill=t.get('background_color','#131f2c' if i%2==0 else '#172331'),outline=BORDER)
   for idx,clip in enumerate(self.clips):
    if clip.get('track')!=t['id']:continue
    x1=left+clip['start']*self.zoom;x2=x1+clip['duration']*self.zoom
    if x2<left or x1>w:continue
    c.create_rectangle(x1,y+8,x2,y+self.rowheight-10,fill=clip.get('color',t.get('clip_color',t.get('color','#26798b'))) if idx!=self.selected else '#8b633c',outline='#6bd4e4',width=1)
    if clip.get('repeat'):
     every=max(.01,float(clip.get('loop_length',clip['duration'])))
     for j in range(1,min(300,int(clip['duration']/every)+1)):
      boundary=x1+j*every*self.zoom
      if boundary<x2:c.create_line(boundary,y+9,boundary,y+self.rowheight-10,fill='#eef1c3',dash=(3,3),width=1)
    for fade_key,flip in [('fade_in',False),('fade_out',True)]:
     fade_pixels=min(x2-x1,max(0,clip.get(fade_key,0))*self.zoom)
     if fade_pixels>1:
      xx=x2-fade_pixels if flip else x1+fade_pixels
      c.create_line(x2 if flip else x1,y+self.rowheight-11,xx,y+9,fill='#eff8ff',width=2)
    c.create_oval(x1+1,y+8,x1+9,y+16,fill=GOLD,outline='');c.create_oval(x2-9,y+8,x2-1,y+16,fill=GOLD,outline='')
    for at,gainpoint in clip.get('automation',[]):
     ax=x1+at*self.zoom;ay=y+self.rowheight-13-max(0,min(1,gainpoint/2))*(self.rowheight-25)
     c.create_oval(ax-3,ay-3,ax+3,ay+3,fill='#ffcf7b',outline='')
    c.create_text(x1+5,y+15,text=clip['file'],anchor='w',fill='white',font=('Segoe UI',8))
    try:
     wave=self.audio(clip['file']);ch=min(clip.get('channel',0),wave.shape[1]-1);offset=int(clip.get('offset',0)*RATE);count=int(clip['duration']*RATE)
     if clip.get('repeat'):
      period=max(1,int(clip.get('loop_length',clip['duration'])*RATE));idxs=offset+np.arange(count,dtype=np.int64)%period;s=wave[idxs[idxs<len(wave)],ch]
     else:s=wave[offset:offset+count,ch]
     bins=max(1,int(min(x2-x1,1000)))
     if len(s):
      mid=y+self.rowheight/2;scale=max(8,(self.rowheight-27)/2)
      c.create_line(max(left,x1),mid,min(w,x2),mid,fill='#527e89')
      first=max(0,int((left-x1)/(x2-x1)*bins)) if x2>x1 else 0
      last=min(bins,int((w-x1)/(x2-x1)*bins)+1) if x2>x1 else bins
      for k in range(first,last):
       a=k*len(s)//bins;b=max(a+1,(k+1)*len(s)//bins);seg=s[a:b]
       if len(seg):
        low=float(np.min(seg));high=float(np.max(seg));cx=x1+(k+.5)*(x2-x1)/bins
        c.create_line(cx,mid-high*scale,cx,mid-low*scale,fill=t.get('waveform_color','#90f0e3'),width=1)
    except Exception:pass
  if self.show_grid.get():
   for idx in range(min(1500,int(end/max(step,.002))+2)):
    sec=idx*step;x=left+sec*self.zoom
    if x>w:break
    isbar=abs(sec/measure-round(sec/measure))<.0001;isbeat=abs(sec/beat-round(sec/beat))<.0001
    c.create_line(x,header,x,height,fill='#718ca8' if isbar else '#536981' if isbeat else '#34475b',width=2 if isbar else 1)
  for idx in range(min(1500,int(end/max(measure,.002))+2)):
   x=left+idx*measure*self.zoom
   if x>w:break
   c.create_text(x+5,43,text=str(idx+1),fill=FG,anchor='w',font=('Segoe UI',9,'bold'))
  if self.loop_playback.get():
   ax=left+self.loop_start.get()*self.zoom;bx=left+self.loop_end.get()*self.zoom
   if bx>ax:c.create_rectangle(ax,31,bx,header,fill='#38565a',stipple='gray50',outline='#68cdb7')
  if self.show_playhead.get():
   px=left+self.position*self.zoom;c.create_line(px,header,px,max(100,len(self.tracks)*self.rowheight+58),fill='#f0b45d',width=2)
  c.configure(scrollregion=(0,0,w,max(300,58+len(self.tracks)*self.rowheight)))
 def snap_time(self,seconds):
  if not self.snap_enabled.get():return max(0,seconds)
  step=(60/max(30,self.bpm.get()))*4/int(self.grid_div.get().split('/')[1])
  return max(0,round(seconds/step)*step)
 def return_start(self):
  if self.running:self.stop()
  self.position=0.;self.draw()
 def click(self,e):
  self.drag=None
  if self.running:return
  if e.y<58 and e.x>=235:
   self.position=self.snap_time((e.x-235)/self.zoom);self.draw();return
  row=int((e.y-58)//self.rowheight)
  if not 0<=row<len(self.tracks):return
  t=self.tracks[row];y=e.y-(58+row*self.rowheight)
  if e.x<235:
   if 35<=y<=56 and 12<=e.x<85:
    idx=int((e.x-12)//26)
    if 0<=idx<3:self.snapshot();key=['arm','mute','solo'][idx];t[key]=not t[key];self.save();self.draw();self.draw_mixer()
   return
  sec=max(0,(e.x-235)/self.zoom)
  self.selected=next((i for i,c in reversed(list(enumerate(self.clips))) if c['track']==t['id'] and c['start']<=sec<=c['start']+c['duration']),None)
  if self.selected is not None:
   clip=self.clips[self.selected];edge_left=235+clip['start']*self.zoom;edge_right=edge_left+clip['duration']*self.zoom
   if 7<=y<=18 and abs(e.x-edge_left)<=12:self.drag=('fade_in',self.selected,e.x,float(clip.get('fade_in',0)))
   elif 7<=y<=18 and abs(e.x-edge_right)<=12:self.drag=('fade_out',self.selected,e.x,float(clip.get('fade_out',0)))
   elif abs(e.x-edge_right)<=9:
    self.drag=('trim_right' if y<self.rowheight/2 else 'loop_right',self.selected,e.x,dict(clip))
   elif abs(e.x-edge_left)<=9 and y<self.rowheight/2:
    self.drag=('trim_left',self.selected,e.x,dict(clip))
   else:self.drag=(self.selected,e.x,clip['start'],row,False)
  else:self.position=self.snap_time(sec)
  self.draw()
 def drag_motion(self,e):
  if not self.drag or self.running:return
  if isinstance(self.drag[0],str):
   key,idx,x0,old=self.drag;clip=self.clips[idx];difference=(e.x-x0)/self.zoom
   if key in ('fade_in','fade_out'):
    clip[key]=max(0.,min(clip['duration'],old+difference*(1 if key=='fade_in' else -1)))
   elif key=='trim_right':
     clip['duration']=max(.03,old.get('loop_length',old['duration'])+difference)
     clip['loop_length']=clip['duration'];clip['repeat']=False
     maxsource=max(.03,len(self.audio(clip['file']))/RATE-clip.get('offset',0))
     clip['duration']=min(clip['duration'],maxsource);clip['loop_length']=clip['duration']
   elif key=='trim_left':
     change=max(-old.get('offset',0),min(old['duration']-.03,difference))
     clip['start']=old['start']+change;clip['offset']=old.get('offset',0)+change
     clip['duration']=old['duration']-change;clip['loop_length']=clip['duration'];clip['repeat']=False
   elif key=='loop_right':
     period=old.get('loop_length',old['duration'])
     clip['loop_length']=period;clip['duration']=max(.03,old['duration']+difference)
     clip['repeat']=clip['duration']>period+0.001
   self.draw();return
  idx,x0,old,row,snapped=self.drag
  clip=self.clips[idx];clip['start']=self.snap_time(old+(e.x-x0)/self.zoom)
  newrow=int((e.y-58)//self.rowheight)
  if 0<=newrow<len(self.tracks):clip['track']=self.tracks[newrow]['id']
  self.draw()
 def drag_release(self,e):
  if self.drag:
   if isinstance(self.drag[0],str):
    key,idx,x0,old=self.drag;updated=dict(self.clips[idx]);self.clips[idx]=old;self.snapshot();self.clips[idx]=updated;self.save();self.drag=None;self.draw();return
   idx,x0,old,row,_=self.drag
   if self.clips[idx]['start']!=old or self.clips[idx]['track']!=self.tracks[row]['id']:
    newstart=self.clips[idx]['start'];newtrack=self.clips[idx]['track']
    self.clips[idx]['start']=old;self.clips[idx]['track']=self.tracks[row]['id'];self.snapshot()
    self.clips[idx]['start']=newstart;self.clips[idx]['track']=newtrack;self.save()
   self.drag=None;self.draw()
 def context(self,e):
  if e.y<58 and e.x>=235:
   self.marker_time=self.snap_time((e.x-235)/self.zoom);self.marker_menu.tk_popup(e.x_root,e.y_root)
  else:self.click(e);self.menu.tk_popup(e.x_root,e.y_root)
 def add_marker(self):
  name=simpledialog.askstring('Song marker','Marker name (anything you like):',parent=self.root)
  if name:
   self.markers.append({'time':self.marker_time,'name':name});self.markers.sort(key=lambda m:m['time']);self.save();self.draw()
 def nearest_marker(self):return min(self.markers,key=lambda m:abs(m['time']-self.marker_time)) if self.markers else None
 def edit_marker(self):
  m=self.nearest_marker()
  if m:
   name=simpledialog.askstring('Rename marker','Marker name:',initialvalue=m['name'],parent=self.root)
   if name:m['name']=name;self.save();self.draw()
 def marker_color(self):
  m=self.nearest_marker()
  if not m:return
  color=colorchooser.askcolor(color=m.get('color',GOLD),title='Marker color',parent=self.root)[1]
  if color:m['color']=color;self.save();self.draw()
 def track_color(self):
  if self.selected is None:return
  c=self.selected_clip()
  t=next((t for t in self.tracks if t['id']==c['track']),None) if c else None
  if not t:return
  color=colorchooser.askcolor(color=t.get('color','#26798b'),title='Track color',parent=self.root)[1]
  if color:t['color']=color;self.save();self.draw();self.draw_mixer()
 def set_fades(self):
  c=self.selected_clip()
  if c is None:return
  fi=simpledialog.askfloat('Fade in','Fade-in duration (seconds)',initialvalue=c.get('fade_in',0),minvalue=0,maxvalue=c['duration'],parent=self.root)
  if fi is None:return
  fo=simpledialog.askfloat('Fade out','Fade-out duration (seconds)',initialvalue=c.get('fade_out',0),minvalue=0,maxvalue=c['duration'],parent=self.root)
  if fo is not None:self.edit(lambda cl:cl.update(fade_in=fi,fade_out=fo))
 def remove_marker(self):
  m=self.nearest_marker()
  if m:self.markers.remove(m);self.save();self.draw()
 def set_dock(self):
  # Adjustable pane is docked within the main layout; side docking changes orientation.
  place=self.dock.get()
  if place=='Window':
   messagebox.showinfo('Mixer window','Detachable mixer is planned for a later update. Choose Bottom, Top, Left or Right.');self.dock.set('Bottom');return
  try:
   self.mainpane.forget(self.mixerpanel);self.mainpane.forget(self.editorrow)
   horizontal=place in ('Left','Right');self.mainpane.configure(orient='horizontal' if horizontal else 'vertical')
   first=self.mixerpanel if place in ('Left','Top') else self.editorrow
   second=self.editorrow if first is self.mixerpanel else self.mixerpanel
   self.mainpane.add(first,minsize=120 if first==self.mixerpanel else 280)
   self.mainpane.add(second,minsize=120 if second==self.mixerpanel else 280)
  except tk.TclError:pass
 def zoom_wheel(self,e):self.zoom=max(12,min(600,self.zoom*(1.15 if e.delta>0 else 1/1.15)));self.draw()
 def height_wheel(self,e):self.rowheight=max(58,min(220,self.rowheight+(10 if e.delta>0 else -10)));self.draw()
 def scroll_wheel(self,e):self.canvas.yview_scroll(-1 if e.delta>0 else 1,'units')
 def selected_clip(self):return self.clips[self.selected] if self.selected is not None and self.selected<len(self.clips) else None
 def edit(self,fn):
  c=self.selected_clip()
  if not c:return
  self.snapshot();fn(c);self.save();self.draw()
 def split(self):
  def f(c):
   p=self.position
   if c['start']<p<c['start']+c['duration']:
    right=dict(c,start=p,offset=c.get('offset',0)+p-c['start'],duration=c['start']+c['duration']-p);c['duration']=p-c['start'];self.clips.append(right)
  self.edit(f)
 def trim(self):
  def f(c):
   lo=max(c['start'],self.loop_start.get());hi=min(c['start']+c['duration'],self.loop_end.get())
   if hi>lo:c['offset']=c.get('offset',0)+lo-c['start'];c['start']=lo;c['duration']=hi-lo
  self.edit(f)
 def move(self):
  p=simpledialog.askfloat('Move','New start time (seconds)',initialvalue=self.position,minvalue=0)
  if p is not None:self.edit(lambda c:c.update(start=p))
 def copy(self):self.edit(lambda c:self.clips.append(dict(c,start=self.position)))
 def clip_gain(self):
  c=self.selected_clip();v=simpledialog.askfloat('Gain','Multiplier',initialvalue=c.get('gain',1),minvalue=0,maxvalue=10) if c else None
  if v is not None:self.edit(lambda c:c.update(gain=v))
 def clip_mute(self):self.edit(lambda c:c.update(mute=not c.get('mute',False)))
 def delete(self):self.edit(lambda c:self.clips.remove(c))
 def draw_mixer(self):
  if not hasattr(self,'mixer'):return
  for child in self.mixer.winfo_children():child.destroy()
  if not self.showmix.get():self.mixer.pack_forget();return
  self.mixer.pack(fill='both',expand=True,padx=4,pady=3);self.meters={};self.input_widgets={}
  for t in self.tracks:
   frame=tk.Frame(self.mixer,bg='#273346',width=104,height=188,highlightthickness=1,highlightbackground=BORDER)
   frame.pack(side='left',padx=2,pady=4);frame.pack_propagate(False)
   tk.Label(frame,text=t['name'][:12],bg=t.get('color','#273346'),fg=FG,font=('Segoe UI Semibold',9)).pack(pady=(2,0))
   meter=tk.Canvas(frame,width=72,height=10,bg='#13202b',highlightthickness=0)
   meter.pack(pady=2);bars=[]
   for n in range(18):
    color='#38bd82' if n<12 else '#e7b65d' if n<16 else '#ef6565'
    bars.append(meter.create_rectangle(n*4,1,n*4+2,9,fill='#293642',outline=''))
   self.meters[t['id']]=(meter,bars)
   tk.Label(frame,text='VOL',bg='#273346',fg=MUTED,font=('Segoe UI',7)).pack()
   gain=tk.Scale(frame,from_=1.5,to=0,orient='vertical',resolution=.01,length=74,sliderlength=11,showvalue=False,bg='#273346',troughcolor='#121b26',highlightthickness=0,bd=0,command=lambda val,track=t:track.update(gain=float(val)))
   gain.set(t['gain']);gain.pack()
   pan=tk.Scale(frame,from_=-1,to=1,orient='horizontal',resolution=.01,length=80,sliderlength=11,showvalue=False,bg='#273346',troughcolor='#121b26',highlightthickness=0,bd=0,command=lambda val,track=t:track.update(pan=float(val)))
   pan.set(t['pan']);pan.pack();self.button(frame,'FX',lambda track=t:self.open_fx(track)).pack(pady=1)
   input_var=tk.StringVar(value=str(t.get('input',1)))
   combo=ttk.Combobox(frame,textvariable=input_var,values=['1 - Input 1','2 - Input 2'],state='readonly',width=11,font=('Segoe UI',8))
   combo.pack(pady=1);combo.bind('<<ComboboxSelected>>',lambda e,track=t,var=input_var:self.set_input(track,var.get()));self.input_widgets[t['id']]=combo
  # Mixer settings are saved with the project
 def tick(self):
  if self.running:self.position=self.playhead/RATE;self.draw()
  self.clock.set(f'{int(self.position//60):02}:{self.position%60:05.2f}')
  try:
   while True:
    msg=self.events.get_nowait()
    if msg=='finished':self.stop()
    else:self.status.set(msg)
  except queue.Empty:pass
  try:
   while True:self.meter_levels.update(self.meter_events.get_nowait())
  except queue.Empty:pass
  for tid,(canvas,bars) in self.meters.items():
   value=self.meter_levels.get(tid,0.)
   target=max(0.,min(1.,(20*math.log10(max(value,1e-6))+48)/48))
   previous=self.meter_smoothed.get(tid,0.)
   smooth=previous+(target-previous)*(.42 if target>previous else .12)
   self.meter_smoothed[tid]=smooth
   for n,bar in enumerate(bars):
    lit=n < round(smooth*18)
    color=('#38bd82' if n<12 else '#e7b65d' if n<16 else '#ef6565') if lit else '#293642'
    canvas.itemconfigure(bar,fill=color)
  self.root.after(75,self.tick)
 def close(self):self.stop_monitor();self.stop();self.save();self.root.destroy()
if __name__=='__main__':
 root=tk.Tk();Studio(root);root.mainloop()
