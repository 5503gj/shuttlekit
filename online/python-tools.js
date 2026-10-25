// A bounded worker RPC: cancellation terminates computation; no Python eval is supplied by users.
export class PythonTools {
 constructor(status){this.status=status;this.worker=null;this.pending=null;this.sequence=0;}
 start(){if(this.worker)return;const worker=this.worker=new Worker(new URL('./worker.js',import.meta.url));worker.onmessage=event=>{const message=event.data;if(this.worker!==worker)return;if(message.type==='status'){this.status(message.text);return;}if(this.pending?.id!==message.id)return;const {resolve,reject}=this.pending;this.pending=null;message.error?reject(new Error(message.error)):resolve(message.result);};worker.onerror=()=>{if(this.pending){this.pending.reject(new Error('计算引擎加载失败，请检查网络后重试。'));this.pending=null;}worker.terminate();if(this.worker===worker)this.worker=null;};}
 call(action,data={}){if(this.pending)return Promise.reject(new Error('上一项任务仍在运行，请稍候或取消。'));this.start();return new Promise((resolve,reject)=>{const id=++this.sequence;this.pending={id,resolve,reject};this.worker.postMessage({id,action,...data});});}
 cancel(){this.sequence++;this.worker?.terminate();this.worker=null;if(this.pending)this.pending.reject(new DOMException('计算已取消','AbortError'));this.pending=null;}
}
