"""Mott Studio 0.1 - offline Windows recording prototype.
MIT licensed project code. Requires sounddevice, soundfile, numpy.
"""
import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
import numpy as np
import sounddevice as sd
import soundfile as sf

RATE=44100
BLOCK=512

class Studio:
    def __init__(self, root):
        self.root=root
        self.root.title('Mott Studio 0.1 | Recording Room')
        self.root.geometry('1050x700')
        self.root.configure(bg='#20242b')
        self.project=None
        self.tracks=[]
        self.device_options=[]
        self.recording=False
        self.playing=False
        self.stream=None
        self.parts=[]
        self.in_q=queue.Queue()
        self.output_frame=0
        self.undo=[]
        self.build_ui()
        self.scan_devices()
        self.root.protocol('WM_DELETE_WINDOW',self.close)

    def build_ui(self):
        m=tk.Menu(self.root)
        filem=tk.Menu(m,tearoff=0)
        filem.add_command(label='New project',command=self.new_project)
        filem.add_command(label='Open project',command=self.open_project)
        filem.add_command(label='Save',command=self.save)
        filem.add_command(label='Export stereo WAV',command=self.export)
        filem.add_separator()
        filem.add_command(label='Exit',command=self.close)
        m.add_cascade(label='File',menu=filem)
        editm=tk.Menu(m,tearoff=0)
        editm.add_command(label='Undo last edit',command=self.undo_edit)
        m.add_cascade(label='Edit',menu=editm)
        self.root.config(menu=m)
        head=ttk.Frame(self.root,padding=12)
        head.pack(fill='x')
        ttk.Label(head,text='MOTT STUDIO • Recording Room',font=('Segoe UI',16,'bold')).pack(anchor='w')
        self.pathlabel=ttk.Label(head,text='No project open • File > New project')
        self.pathlabel.pack(anchor='w')
        devices=ttk.Frame(self.root,padding=(12,2,12,6));devices.pack(fill='x')
        ttk.Label(devices,text='Audio input').pack(side='left')
        self.device=tk.StringVar()
        self.device_combo=ttk.Combobox(devices,textvariable=self.device,width=52,state='readonly')
        self.device_combo.pack(side='left',padx=8)
        ttk.Button(devices,text='Refresh devices',command=self.scan_devices).pack(side='left')
        ttk.Label(devices,text='Input channels (1=mic, 2=guitar)').pack(side='left',padx=(15,4))
        self.channels=tk.IntVar(value=2)
        ttk.Spinbox(devices,from_=1,to=2,textvariable=self.channels,width=4).pack(side='left')
        transport=ttk.Frame(self.root,padding=12); transport.pack(fill='x')
        self.record_btn=ttk.Button(transport,text='● RECORD',command=self.record)
        self.record_btn.pack(side='left',padx=4)
        self.stop_btn=ttk.Button(transport,text='■ STOP',command=self.stop)
        self.stop_btn.pack(side='left',padx=4)
        self.play_btn=ttk.Button(transport,text='▶ PLAY',command=self.play)
        self.play_btn.pack(side='left',padx=4)
        ttk.Button(transport,text='Export WAV',command=self.export).pack(side='left',padx=4)
        self.status=tk.StringVar(value='Create a project to begin. Use headphones for monitoring through your interface.')
        ttk.Label(self.root,textvariable=self.status,padding=10,wraplength=980).pack(anchor='w')
        self.tree=ttk.Treeview(self.root,columns=('type','start','length','gain','mute'),show='headings',height=13,selectmode='browse')
        for col,width in [('type',220),('start',120),('length',120),('gain',100),('mute',80)]:
            self.tree.heading(col,text={'type':'Track / clip','start':'Start (s)','length':'Duration (s)','gain':'Gain','mute':'Muted'}[col])
            self.tree.column(col,width=width)
        self.tree.pack(fill='both',expand=True,padx=12,pady=8)
        action=ttk.Frame(self.root,padding=12);action.pack(fill='x')
        for label,cmd in [('Split at time',self.split),('Trim selection',self.trim),('Move clip',self.move),('Copy clip',self.copy),('Gain / volume',self.gain),('Mute/unmute',self.mute),('Delete clip',self.delete),('Undo',self.undo_edit)]:
            ttk.Button(action,text=label,command=cmd).pack(side='left',padx=3,pady=3)
        ttk.Label(self.root,text='Select a clip to edit. This prototype saves non-destructive edits in project.json. Audio files remain intact.',padding=12).pack(anchor='w')
        self.root.after(150,self.poll)

    def scan_devices(self):
        self.device_options=[]
        for i,d in enumerate(sd.query_devices()):
            if d['max_input_channels']>0:
                self.device_options.append((f"{i}: {d['name']} ({d['max_input_channels']} inputs)",i,d['max_input_channels']))
        self.device_combo['values']=[x[0] for x in self.device_options]
        preferred=next((x[0] for x in self.device_options if 'scarlett' in x[0].lower() or 'irig' in x[0].lower()),None)
        if self.device_options:
            self.device.set(preferred or self.device_options[0][0])
        else:self.status.set('No recording input found. Connect an interface and click Refresh devices.')

    def selected_device(self):
        return next((x for x in self.device_options if x[0]==self.device.get()),None)

    def new_project(self):
        if self.recording:return
        folder=filedialog.askdirectory(title='Choose a folder for your song')
        if not folder:return
        name=simpledialog.askstring('Project name','Name this song / session:',parent=self.root)
        if not name:return
        name=''.join(c if c.isalnum() or c in ' -_' else '_' for c in name).strip() or 'Untitled'
        dest=Path(folder)/name
        if dest.exists() and any(dest.iterdir()):
            messagebox.showerror('Folder exists','Choose a new project name or use Open project.');return
        dest.mkdir(parents=True,exist_ok=True)
        (dest/'audio').mkdir(exist_ok=True)
        self.project=dest;self.tracks=[];self.refresh();self.save()

    def open_project(self):
        folder=filedialog.askdirectory(title='Select an existing Mott Studio project folder')
        if not folder:return
        dest=Path(folder)
        try:
            data=json.loads((dest/'project.json').read_text(encoding='utf-8'))
            self.project=dest;self.tracks=data['clips'];self.refresh()
        except Exception as e:messagebox.showerror('Open failed',str(e))

    def save(self):
        if not self.project:return
        obj={'format':'mott-studio-0.1','sample_rate':RATE,'clips':self.tracks}
        tmp=self.project/'project.tmp';tmp.write_text(json.dumps(obj,indent=2),encoding='utf-8')
        os.replace(tmp,self.project/'project.json')
        self.pathlabel.config(text=str(self.project))
        self.status.set('Project saved.')

    def refresh(self):
        for i in self.tree.get_children():self.tree.delete(i)
        for i,t in enumerate(self.tracks):
            self.tree.insert('', 'end',iid=str(i),values=(t['name'],f"{t['start']:.2f}",f"{t['duration']:.2f}",f"{t['gain']:.2f}",'yes' if t['mute'] else 'no'))
        if self.project:self.pathlabel.config(text=str(self.project))

    def selected(self):
        ids=self.tree.selection()
        if not ids:messagebox.showinfo('Select clip','Choose a clip in the list first.');return None
        return int(ids[0])

    def push_undo(self):
        self.undo.append(json.loads(json.dumps(self.tracks)))
        if len(self.undo)>30:self.undo.pop(0)

    def undo_edit(self):
        if self.undo:self.tracks=self.undo.pop();self.refresh();self.save()

    def record(self):
        if not self.project:messagebox.showinfo('New project','Create a project first.');return
        if self.recording or self.playing:return
        selected=self.selected_device()
        if not selected:messagebox.showerror('Audio device','Select a recording device.');return
        chans=min(max(1,self.channels.get()),selected[2])
        self.parts=[];self.recording=True;self.status.set('Recording... click STOP to finish.')
        def callback(indata,frames,time_info,status):
            if status:self.in_q.put(('status',str(status)))
            self.parts.append(indata.copy())
        try:
            self.stream=sd.InputStream(device=selected[1],samplerate=RATE,channels=chans,blocksize=BLOCK,callback=callback)
            self.stream.start()
        except Exception as e:
            self.recording=False;self.status.set('Recording could not start. Check audio device / sample rate.')
            messagebox.showerror('Recording failed',str(e))

    def stop(self):
        if self.recording:
            self.recording=False
            if self.stream:
                self.stream.stop();self.stream.close();self.stream=None
            if self.parts:
                arr=np.concatenate(self.parts)
                filename=f'take_{int(time.time()*1000)}.wav'
                sf.write(self.project/'audio'/filename,arr,RATE,subtype='PCM_24')
                self.push_undo()
                length=len(arr)/RATE
                # Each channel is an independent mono clip, linked to one source recording.
                for ch in range(arr.shape[1]):
                    self.tracks.append({'name':('Vocal' if ch==0 else 'Guitar')+f' | {filename}', 'file':filename,'channel':ch,'start':0.0,'offset':0.0,'duration':length,'gain':1.0,'mute':False})
                self.refresh();self.save();self.status.set(f'Saved {length:.1f}s recording to project audio folder.')
            else:self.status.set('No audio captured.')
        if self.playing:
            self.playing=False
            if self.stream:
                self.stream.stop();self.stream.close();self.stream=None
            self.status.set('Playback stopped.')

    def ask_time(self,title,initial):
        return simpledialog.askfloat(title,'Time in seconds:',initialvalue=initial,minvalue=0,parent=self.root)

    def split(self):
        idx=self.selected()
        if idx is None:return
        t=self.tracks[idx]
        pos=self.ask_time('Split clip',round(t['start']+t['duration']/2,2))
        if pos is None:return
        local=pos-t['start']
        if not (0<local<t['duration']):messagebox.showerror('Invalid split','Time must fall inside selected clip.');return
        self.push_undo()
        right=dict(t,start=pos,offset=t['offset']+local,duration=t['duration']-local)
        t['duration']=local
        self.tracks.insert(idx+1,right);self.refresh();self.save()

    def trim(self):
        idx=self.selected()
        if idx is None:return
        t=self.tracks[idx]
        start=self.ask_time('Trim: new beginning',t['start'])
        if start is None:return
        end=self.ask_time('Trim: new ending',t['start']+t['duration'])
        if end is None:return
        if start<t['start'] or end>t['start']+t['duration'] or end<=start:
            messagebox.showerror('Invalid trim','Choose times within the current clip, with end after start.');return
        self.push_undo();t['offset']+=start-t['start'];t['start']=start;t['duration']=end-start;self.refresh();self.save()

    def move(self):
        idx=self.selected()
        if idx is None:return
        pos=self.ask_time('Move clip',self.tracks[idx]['start'])
        if pos is None:return
        self.push_undo();self.tracks[idx]['start']=pos;self.refresh();self.save()

    def copy(self):
        idx=self.selected()
        if idx is None:return
        t=self.tracks[idx];pos=self.ask_time('Paste copied clip at',t['start']+t['duration'])
        if pos is None:return
        self.push_undo();self.tracks.append(dict(t,start=pos,name=t['name']+' (copy)'));self.refresh();self.save()

    def gain(self):
        idx=self.selected()
        if idx is None:return
        v=simpledialog.askfloat('Clip gain','Multiplier (0=silent, 1=unchanged, 2=twice amplitude)',initialvalue=self.tracks[idx]['gain'],minvalue=0,maxvalue=10,parent=self.root)
        if v is None:return
        self.push_undo();self.tracks[idx]['gain']=v;self.refresh();self.save()

    def mute(self):
        idx=self.selected()
        if idx is None:return
        self.push_undo();self.tracks[idx]['mute']=not self.tracks[idx]['mute'];self.refresh();self.save()

    def delete(self):
        idx=self.selected()
        if idx is None:return
        self.push_undo();self.tracks.pop(idx);self.refresh();self.save()

    def mix(self):
        if not self.project or not self.tracks:return np.zeros((0,2),dtype=np.float32)
        total=int(max(t['start']+t['duration'] for t in self.tracks)*RATE)+1
        if total>RATE*60*45:raise ValueError('Maximum export duration is 45 minutes in this prototype.')
        out=np.zeros((total,2),dtype=np.float32)
        cache={}
        for t in self.tracks:
            if t['mute']:continue
            if t['file'] not in cache:
                audio,r=sf.read(self.project/'audio'/t['file'],always_2d=True,dtype='float32')
                if r!=RATE:raise ValueError(f'Unsupported sample rate for {t["file"]}: {r}')
                cache[t['file']]=audio
            audio=cache[t['file']]
            channel=min(t['channel'],audio.shape[1]-1)
            source=int(t['offset']*RATE);count=int(t['duration']*RATE)
            sample=audio[source:source+count,channel]*t['gain']
            st=int(t['start']*RATE)
            if st+len(sample)>len(out):sample=sample[:len(out)-st]
            out[st:st+len(sample),:]+=sample[:,None]
        peak=float(np.max(np.abs(out))) if len(out) else 0
        if peak>1:out/=peak;self.status.set('Mix normalized to prevent clipping.')
        return out

    def play(self):
        if self.recording or self.playing:return
        try:
            data=self.mix()
            if not len(data):return
            self.playing=True;self.output_frame=0
            def callback(outdata,frames,t,status):
                end=min(self.output_frame+frames,len(data))
                n=end-self.output_frame
                outdata[:n]=data[self.output_frame:end]
                if n<frames:outdata[n:]=0;raise sd.CallbackStop
                self.output_frame=end
            def finished():self.in_q.put(('ended','Playback finished.'))
            self.stream=sd.OutputStream(samplerate=RATE,channels=2,blocksize=BLOCK,callback=callback,finished_callback=finished)
            self.stream.start();self.status.set('Playing mix...')
        except Exception as e:
            self.playing=False;messagebox.showerror('Playback failed',str(e))

    def export(self):
        if not self.project:return
        try:
            data=self.mix()
            if not len(data):messagebox.showinfo('No audio','Record something first.');return
            filename=filedialog.asksaveasfilename(title='Export WAV',defaultextension='.wav',filetypes=[('WAV audio','*.wav')],initialdir=str(self.project),initialfile=self.project.name+'_mix.wav')
            if filename:sf.write(filename,data,RATE,subtype='PCM_24');self.status.set('Exported WAV: '+filename)
        except Exception as e:messagebox.showerror('Export failed',str(e))

    def poll(self):
        try:
            while True:
                key,val=self.in_q.get_nowait()
                if key=='ended':
                    self.playing=False
                    if self.stream:self.stream.close();self.stream=None
                self.status.set(val)
        except queue.Empty:pass
        self.root.after(150,self.poll)

    def close(self):
        self.stop()
        if self.project:self.save()
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk()
    try:Studio(root);root.mainloop()
    except Exception as exc:messagebox.showerror('Startup error',str(exc));raise
