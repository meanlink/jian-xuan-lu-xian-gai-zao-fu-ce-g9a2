import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const lines={list:()=>api('/lines'),board:()=>api('/lines/board'),get:id=>api('/lines/'+id),create:data=>api('/lines',{method:'POST',body:JSON.stringify(data)}),handover:(id,data)=>api('/lines/'+id+'/handover',{method:'POST',body:JSON.stringify(data)}),cancel:(id,data)=>api('/lines/'+id+'/cancel',{method:'POST',body:JSON.stringify(data)})};
