"""Mott Studio 2.4.1 beta: multitrack DAW. MIT license."""
import json, os, time, uuid, queue, threading, math
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import numpy as np
import sounddevice as sd
import soundfile as sf

RATE=44100; BLOCK=512
BG='#0d1118'; PANEL='#1a2230'; FG='#edf3fa'; GOLD='#e6b56a'; BLUE='#48b4d4'; BORDER='#303d50'; MUTED='#8ea1b6'
class Studio:
 def __init__(self,root):
  self.root=root;root.title('Mott Studio 2.4.1 | Songwriting Workspace');root.geometry('1380x860');root.minsize(940,610);root.configure(bg=BG)
  self.project=None;self.tracks=[];self.clips=[];self.undo=[];self.selected=None;self.mode=tk.StringVar(value='Normal');self.device=tk.StringVar();self.output=tk.StringVar();self.devices=[];self.outputs=[]
  self.position=0.;self.zoom=85.;self.rowheight=88;self.running=False;self.stream=None;self.recorded=[];self.capture_start=0;self.playhead=0;self.meters={};self.events=queue.Queue();self.cache={};self.loop_start=tk.DoubleVar(value=0);self.loop_end=tk.DoubleVar(value=8);self.countin=tk.BooleanVar(value=False);self.metronome=tk.BooleanVar(value=False);self.bpm=tk.IntVar(value=120);self.tap_times=[];self.input_widgets={};self.active_inputs={};self.meter_levels={};self.meter_events=queue.Queue();self.meter_smoothed={};self.markers=[];self.lyrics='';self.drag=None;self.snap_enabled=tk.BooleanVar(value=True);self.grid_div=tk.StringVar(value='1/16');self.signature=tk.IntVar(value=4);self.master_gain=tk.DoubleVar(value=1.0);self.record_origin=0.;self.dock=tk.StringVar(value='Bottom');self.notes_visible=tk.BooleanVar(value=True)
  self.build();self.scan();root.after(80,self.tick);root.protocol('WM_DELETE_WINDOW',self.close)
 def button(self,parent,label,command):return tk.Button(parent,text=label,command=command,bg='#29384a',fg=FG,activebackground='#415672',activeforeground='white',relief='flat',padx=13,pady=8,font=('Segoe UI Semibold',10),cursor='hand2',bd=0)
 def build(self):
  style=ttk.Style(self.root)
  try:style.theme_use('clam')
  except tk.TclError:pass
  style.configure('TCombobox',fieldbackground='#233044',background='#233044',foreground='#10151b',padding=5)
  style.configure('TScrollbar',background=PANEL,troughcolor=BG)
  menu=tk.Menu(self.root);f=tk.Menu(menu,tearoff=False)
  for label,fn in [('New project',self.new),('Open project',self.open),('Save',self.save),('Import WAV',self.import_wav),('Export stereo WAV',self.export),('Exit',self.close)]:f.add_command(label=label,command=fn)
  menu.add_cascade(label='File',menu=f);e=tk.Menu(menu,tearoff=False);e.add_command(label='Undo',command=self.undo_edit);e.add_command(label='Split clip at playhead',command=self.split);menu.add_cascade(label='Edit',menu=e);self.root.config(menu=menu);self.root.bind('<Control-z>',lambda e:self.undo_edit());self.root.bind('<KeyPress-s>',lambda e:self.split() if not isinstance(e.widget,(tk.Entry,tk.Text,ttk.Combobox)) else None)
  top=tk.Frame(self.root,bg=BG);top.pack(fill='x',padx=14,pady=8)
  tk.Label(top,text='MOTT / STUDIO',bg=BG,fg=FG,font=('Segoe UI Semibold',24)).pack(side='left');tk.Label(top,text='    2.4.1  •  SONGWRITING WORKSPACE',bg=BG,fg=GOLD,font=('Segoe UI Semibold',10)).pack(side='left')
  self.status=tk.StringVar(value='Create or open a project to begin.');tk.Label(self.root,textvariable=self.status,bg=BG,fg='#b9c5ce',anchor='w').pack(fill='x',padx=16)
  controls=tk.Frame(self.root,bg=PANEL,highlightbackground=BORDER,highlightthickness=1);controls.pack(fill='x',padx=12,pady=7)
  for label,fn in [('● REC',self.record),('▶ PLAY',self.play),('■ STOP',self.stop),('+ TRACK',self.add_track),('IMPORT',self.import_wav),('EXPORT',self.export)]:
   b=self.button(controls,label,fn);b.pack(side='left',padx=4,pady=8)
   if 'REC' in label:b.configure(bg='#a53e48',activebackground='#c8565e')
   elif 'PLAY' in label:b.configure(bg='#1c7869',activebackground='#2a9d82')
  ttk.Combobox(controls,textvariable=self.mode,values=['Normal','Time selection','Punch','Loop takes'],width=17,state='readonly').pack(side='left',padx=7)
  tk.Checkbutton(controls,text='Click',variable=self.metronome,bg=PANEL,fg=FG,selectcolor=BG).pack(side='left')
  tk.Checkbutton(controls,text='Count-in',variable=self.countin,bg=PANEL,fg=FG,selectcolor=BG).pack(side='left')
  tk.Label(controls,text='BPM',bg=PANEL,fg=FG).pack(side='left',padx=(8,2));tk.Spinbox(controls,from_=30,to=300,textvariable=self.bpm,width=4).pack(side='left');self.button(controls,'TAP',self.tap_tempo).pack(side='left',padx=3);tk.Label(controls,text='Grid',bg=PANEL,fg=FG).pack(side='left');ttk.Combobox(controls,textvariable=self.grid_div,values=['1/1','1/2','1/4','1/8','1/16','1/32'],width=5,state='readonly').pack(side='left');tk.Checkbutton(controls,text='Snap',variable=self.snap_enabled,bg=PANEL,fg=FG,selectcolor=BG).pack(side='left');self.button(controls,'|◀ Start',self.return_start).pack(side='left',padx=3)
  devices=tk.Frame(self.root,bg=BG);devices.pack(fill='x',padx=12)
  tk.Label(devices,text='Input:',bg=BG,fg=FG).pack(side='left');self.indev=ttk.Combobox(devices,textvariable=self.device,width=36,state='readonly');self.indev.pack(side='left',padx=5)
  tk.Label(devices,text='Output:',bg=BG,fg=FG).pack(side='left');self.outdev=ttk.Combobox(devices,textvariable=self.output,width=36,state='readonly');self.outdev.pack(side='left',padx=5);self.button(devices,'Refresh',self.scan).pack(side='left')
  bar=tk.Frame(self.root,bg=BG);bar.pack(fill='x',padx=14,pady=5)
  for label,var in [('Selection start (s)',self.loop_start),('End (s)',self.loop_end)]:tk.Label(bar,text=label,bg=BG,fg=FG).pack(side='left');tk.Entry(bar,textvariable=var,width=7).pack(side='left',padx=6)
  self.clock=tk.StringVar(value='00:00.00');tk.Label(bar,textvariable=self.clock,bg=BG,fg=GOLD,font=('Consolas',23,'bold')).pack(side='right')
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

  self.canvas.bind('<Button-1>',self.click);self.canvas.bind('<B1-Motion>',self.drag_motion);self.canvas.bind('<ButtonRelease-1>',self.drag_release);self.canvas.bind('<Button-3>',self.context);self.canvas.bind('<Control-MouseWheel>',self.zoom_wheel);self.canvas.bind('<Shift-MouseWheel>',self.height_wheel);self.canvas.bind('<MouseWheel>',self.scroll_wheel);self.canvas.bind('<Configure>',lambda e:self.draw())
  self.menu=tk.Menu(self.root,tearoff=0);self.marker_menu=tk.Menu(self.root,tearoff=0);self.marker_menu.add_command(label='Add marker here',command=self.add_marker);self.marker_menu.add_command(label='Edit nearest marker',command=self.edit_marker);self.marker_menu.add_command(label='Remove nearest marker',command=self.remove_marker)
  for label,fn in [('Split at playhead',self.split),('Trim to selection',self.trim),('Move clip',self.move),('Copy clip',self.copy),('Clip gain',self.clip_gain),('Mute/unmute clip',self.clip_mute),('Delete clip',self.delete)]:self.menu.add_command(label=label,command=fn)
  mixhead=tk.Frame(self.mixerpanel,bg=BG);mixhead.pack(fill='x',padx=6);tk.Label(mixhead,text='MIX CONSOLE',bg=BG,fg=GOLD,font=('Segoe UI Semibold',11)).pack(side='left');self.showmix=tk.BooleanVar(value=True);tk.Checkbutton(mixhead,text='Show mixer',variable=self.showmix,command=self.draw_mixer,bg=BG,fg=FG,selectcolor=PANEL).pack(side='right')
  tk.Label(mixhead,text='Dock',bg=BG,fg=FG).pack(side='left',padx=(15,3));dock_selector=ttk.Combobox(mixhead,textvariable=self.dock,values=['Bottom','Top','Left','Right','Window'],width=8,state='readonly');dock_selector.pack(side='left');dock_selector.bind('<<ComboboxSelected>>',lambda e:self.set_dock())
  tk.Label(mixhead,text='Master',bg=BG,fg=FG).pack(side='left',padx=(15,3));tk.Scale(mixhead,from_=0,to=2,orient='horizontal',variable=self.master_gain,resolution=.05,length=110,bg=BG,fg=FG,highlightthickness=0).pack(side='left')
  self.mixer=tk.Frame(self.mixerpanel,bg=PANEL,height=190);self.mixer.pack(fill='both',expand=True,padx=4,pady=2);self.draw()
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
   self.project=Path(folder);obj=json.loads((self.project/'project.json').read_text());self.tracks=obj.get('tracks',[]);self.clips=obj.get('clips',[]);self.markers=obj.get('markers',[]);self.lyrics=obj.get('lyrics','');self.lyrictext.delete('1.0','end');self.lyrictext.insert('1.0',self.lyrics);self.bpm.set(obj.get('bpm',120));self.signature.set(obj.get('signature',4));self.master_gain.set(obj.get('master_gain',1.0))
   if not self.tracks:
    old=self.clips;self.clips=[]
    for i,c in enumerate(old):self.add_track(c.get('name',f'Track {i+1}'));c['track']=self.tracks[-1]['id'];self.clips.append(c)
   self.cache.clear();self.draw();self.draw_mixer();self.status.set(f'Opened {folder}')
  except Exception as exc:messagebox.showerror('Open failed',str(exc))
 def save(self):
  if not self.project:return
  data={'format':'mott-studio-2.4','sample_rate':RATE,'tracks':self.tracks,'clips':self.clips,'markers':self.markers,'lyrics':self.lyrictext.get('1.0','end-1c') if hasattr(self,'lyrictext') else self.lyrics,'bpm':self.bpm.get(),'signature':self.signature.get(),'master_gain':self.master_gain.get()};tmp=self.project/'project.tmp';tmp.write_text(json.dumps(data,indent=2));os.replace(tmp,self.project/'project.json');self.status.set('Project saved: '+str(self.project))
 def add_track(self,name=None):
  if not self.project:
   create=messagebox.askyesno('Project required', 'Tracks need a project to save into.\n\nCreate a new project now?\n\nChoose No to cancel and open an existing project from File > Open project.')
   if create:
    self.new()  # New project creates Track 1 automatically.
   return
  if not isinstance(name,str):name=f'Track {len(self.tracks)+1}'
  self.snapshot()
  self.tracks.append({'id':uuid.uuid4().hex,'name':name,'input':min(len(self.tracks)+1,2),'arm':True,'mute':False,'solo':False,'gain':1.,'pan':0.});self.draw();self.draw_mixer();self.save()
 def snapshot(self):self.undo.append(json.loads(json.dumps((self.tracks,self.clips))));self.undo=self.undo[-30:]
 def undo_edit(self):
  if self.undo:self.tracks,self.clips=self.undo.pop();self.draw();self.draw_mixer();self.save()
 def audio(self,filename):
  if filename not in self.cache:
   a,r=sf.read(self.project/'audio'/filename,always_2d=True,dtype='float32')
   if r!=RATE:raise ValueError(f'{filename}: sample rate must be 44100 Hz')
   self.cache[filename]=a
  return self.cache[filename]
 def mix_block(self,start,n):
  out=np.zeros((n,2),dtype=np.float32);solos=any(t['solo'] for t in self.tracks)
  for t in self.tracks:
   if t['mute'] or (solos and not t['solo']):continue
   for c in self.clips:
    if c.get('track')!=t['id'] or c.get('mute'):continue
    cs=round(c['start']*RATE);ce=cs+round(c['duration']*RATE);a=max(start,cs);b=min(start+n,ce)
    if b<=a:continue
    source=round(c.get('offset',0)*RATE)+(a-cs);wave=self.audio(c['file']);ch=min(c.get('channel',0),wave.shape[1]-1);segment=wave[source:source+(b-a),ch]
    if not len(segment):continue
    gain=c.get('gain',1)*t['gain'];pan=t['pan'];out[a-start:a-start+len(segment),0]+=segment*gain*min(1,1-pan);out[a-start:a-start+len(segment),1]+=segment*gain*min(1,1+pan)
  return out*self.master_gain.get()
 def total(self):return max([c['start']+c['duration'] for c in self.clips]+[0])
 def play(self):self.start(False)
 def record(self):self.start(True)
 def start(self,record):
  if self.running:return
  if not self.project:messagebox.showinfo('Project','Create a project first');return
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
     if not self.is_record and self.playhead>=int(self.total()*RATE):raise sd.CallbackStop
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
 def draw(self):
  if not hasattr(self,'canvas'):return
  c=self.canvas;c.delete('all');w=max(c.winfo_width(),100);left=235;end=max(0,(w-left)/self.zoom)
  beat=60/max(30,self.bpm.get());measure=beat*max(1,self.signature.get());step=beat*4/int(self.grid_div.get().split('/')[1]);height=max(100,len(self.tracks)*self.rowheight+36)
  for idx in range(min(1500,int(end/max(step,.002))+2)):
   sec=idx*step;x=left+sec*self.zoom
   if x>w:break
   isbar=abs(sec/measure-round(sec/measure))<.0001;isbeat=abs(sec/beat-round(sec/beat))<.0001
   c.create_line(x,0,x,height,fill='#41516a' if isbar else '#29394d' if isbeat else '#202d3e',width=2 if isbar else 1)
   if isbar:c.create_text(x+5,12,text=str(round(sec/measure)+1),fill=FG,anchor='w',font=('Segoe UI',10,'bold'))
  for m in self.markers:
   x=left+m['time']*self.zoom
   if left<=x<=w:
    c.create_line(x,20,x,height,fill=GOLD,dash=(4,4));c.create_text(x+3,25,text=m['name'][:24],anchor='nw',fill=GOLD,font=('Segoe UI',9,'bold'))
  for i,t in enumerate(self.tracks):
   y=36+i*self.rowheight;c.create_rectangle(0,y,left,y+self.rowheight-2,fill='#1f2b3a',outline=BORDER);c.create_text(12,y+20,text=t['name'],fill=FG,anchor='w',font=('Segoe UI',11,'bold'))
   for j,(label,key,color) in enumerate([('R','arm','#e84d4d'),('M','mute','#43b86a'),('S','solo','#f0c64d')]):
    x=12+j*45
    if key=='arm':c.create_oval(x,y+40,x+30,y+70,fill=color if t[key] else '#46515d',outline='#f4a3a3' if t[key] else '#65717b',width=2)
    else:c.create_rectangle(x,y+40,x+35,y+70,fill=color if t[key] else '#46515d',outline='')
    c.create_text(x+16,y+55,text=label,fill='#11171c' if t[key] else FG,font=('Segoe UI',10,'bold'))
   c.create_text(150,y+55,text=f'IN {t.get("input",1)}',fill=GOLD,font=('Segoe UI',9,'bold'))
   level=self.meter_levels.get(t['id'],0.) if self.running else 0.
   fraction=max(0.,min(1.,(20*math.log10(max(level,1e-6))+48)/48))
   c.create_rectangle(142,y+67,222,y+75,fill='#273c48',outline='#485665')
   c.create_rectangle(142,y+67,142+80*fraction,y+75,fill='#5ad5aa',outline='')
   c.create_rectangle(left,y,w,y+self.rowheight-2,fill='#131f2c' if i%2==0 else '#172331',outline=BORDER)
   for idx,clip in enumerate(self.clips):
    if clip.get('track')!=t['id']:continue
    x1=left+clip['start']*self.zoom;x2=x1+clip['duration']*self.zoom
    if x2<left or x1>w:continue
    c.create_rectangle(x1,y+8,x2,y+self.rowheight-10,fill='#1c6474' if idx!=self.selected else '#8b633c',outline='#6bd4e4',width=1)
    c.create_text(x1+5,y+15,text=clip['file'],anchor='w',fill='white',font=('Segoe UI',8))
    try:
     wave=self.audio(clip['file']);ch=min(clip.get('channel',0),wave.shape[1]-1);offset=int(clip.get('offset',0)*RATE);count=int(clip['duration']*RATE);s=wave[offset:offset+count,ch];bins=max(1,int(min(x2-x1,1000)))
     if len(s):
      mid=y+self.rowheight/2;scale=max(8,(self.rowheight-27)/2)
      c.create_line(max(left,x1),mid,min(w,x2),mid,fill='#527e89')
      first=max(0,int((left-x1)/(x2-x1)*bins)) if x2>x1 else 0
      last=min(bins,int((w-x1)/(x2-x1)*bins)+1) if x2>x1 else bins
      for k in range(first,last):
       a=k*len(s)//bins;b=max(a+1,(k+1)*len(s)//bins);seg=s[a:b]
       if len(seg):
        low=float(np.min(seg));high=float(np.max(seg));cx=x1+(k+.5)*(x2-x1)/bins
        c.create_line(cx,mid-high*scale,cx,mid-low*scale,fill='#90f0e3',width=1)
    except Exception:pass
  px=left+self.position*self.zoom;c.create_line(px,0,px,max(100,len(self.tracks)*self.rowheight+36),fill='#f0b45d',width=2)
  c.configure(scrollregion=(0,0,w,max(300,36+len(self.tracks)*self.rowheight)))
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
  if e.y<36 and e.x>=235:
   self.position=self.snap_time((e.x-235)/self.zoom);self.draw();return
  row=int((e.y-36)//self.rowheight)
  if not 0<=row<len(self.tracks):return
  t=self.tracks[row];y=e.y-(36+row*self.rowheight)
  if e.x<235:
   if 40<=y<=70:
    idx=int((e.x-12)//45)
    if 0<=idx<3:self.snapshot();key=['arm','mute','solo'][idx];t[key]=not t[key];self.save();self.draw();self.draw_mixer()
   return
  sec=max(0,(e.x-235)/self.zoom)
  self.selected=next((i for i,c in reversed(list(enumerate(self.clips))) if c['track']==t['id'] and c['start']<=sec<=c['start']+c['duration']),None)
  if self.selected is not None:
   clip=self.clips[self.selected];self.drag=(self.selected,e.x,clip['start'],row,False)
  else:self.position=self.snap_time(sec)
  self.draw()
 def drag_motion(self,e):
  if not self.drag or self.running:return
  idx,x0,old,row,snapped=self.drag
  clip=self.clips[idx];clip['start']=self.snap_time(old+(e.x-x0)/self.zoom)
  newrow=int((e.y-36)//self.rowheight)
  if 0<=newrow<len(self.tracks):clip['track']=self.tracks[newrow]['id']
  self.draw()
 def drag_release(self,e):
  if self.drag:
   idx,x0,old,row,_=self.drag
   if self.clips[idx]['start']!=old or self.clips[idx]['track']!=self.tracks[row]['id']:
    newstart=self.clips[idx]['start'];newtrack=self.clips[idx]['track']
    self.clips[idx]['start']=old;self.clips[idx]['track']=self.tracks[row]['id'];self.snapshot()
    self.clips[idx]['start']=newstart;self.clips[idx]['track']=newtrack;self.save()
   self.drag=None;self.draw()
 def context(self,e):
  if e.y<36 and e.x>=235:
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
  for t in self.tracks[:12]:
   frame=tk.Frame(self.mixer,bg='#273346',width=148,highlightthickness=1,highlightbackground=BORDER);frame.pack(side='left',padx=4,pady=7);frame.pack_propagate(False)
   tk.Label(frame,text=t['name'][:13],bg='#273346',fg=FG,font=('Segoe UI',9)).pack()
   meter=tk.Canvas(frame,width=128,height=65,bg='#ead7a6',highlightthickness=0);meter.pack(pady=2);meter.create_arc(12,16,116,104,start=28,extent=124,style='arc',outline='#655b44',width=2);needle=meter.create_line(64,57,31,38,fill='#a33e2f',width=2);meter.create_text(64,11,text='MOTT  •  VU',font=('Segoe UI',8,'bold'),fill='#3b3325');meter.create_text(20,49,text='-20',font=('Segoe UI',7),fill='#655b44');meter.create_text(108,49,text='+3',font=('Segoe UI',7),fill='#9c3930');self.meters[t['id']]=(meter,needle)
   scale=tk.Scale(frame,from_=2,to=0,orient='vertical',resolution=.05,length=85,showvalue=False,bg='#273346',fg=FG,highlightthickness=0,command=lambda val,track=t:track.update(gain=float(val)));scale.set(t['gain']);scale.pack(side='left')
   right=tk.Frame(frame,bg='#303941');right.pack(side='left');tk.Label(right,text='PAN',bg='#273346',fg=FG).pack();pan=tk.Scale(right,from_=-1,to=1,orient='horizontal',resolution=.1,length=55,showvalue=False,bg='#303941',highlightthickness=0,command=lambda val,track=t:track.update(pan=float(val)));pan.set(t['pan']);pan.pack();tk.Label(right,text='INPUT',bg='#303941',fg=GOLD).pack()
   input_var=tk.StringVar(value=f'{t.get("input",1)} - Input {t.get("input",1)}')
   combo=ttk.Combobox(right,textvariable=input_var,values=['1 - Input 1','2 - Input 2'],state='readonly',width=11)
   combo.pack();combo.bind('<<ComboboxSelected>>',lambda e,track=t,var=input_var:self.set_input(track,var.get()));self.input_widgets[t['id']]=combo
   frame.configure(height=230)
  self.button(self.mixer,'Save mixer',self.save).pack(side='right',padx=10)
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
  for tid,(canvas,needle) in self.meters.items():
   value=self.meter_levels.get(tid,0.) if self.running else 0.
   target=max(0.,min(1.,(20*math.log10(max(value,1e-6))+48)/48))
   previous=self.meter_smoothed.get(tid,0.)
   smooth=previous+(target-previous)*(.42 if target>previous else .12)
   self.meter_smoothed[tid]=smooth
   theta=math.radians(150-120*smooth)
   canvas.coords(needle,64,57,64+42*math.cos(theta),57-42*math.sin(theta))
  self.root.after(75,self.tick)
 def close(self):self.stop();self.save();self.root.destroy()
if __name__=='__main__':
 root=tk.Tk();Studio(root);root.mainloop()
