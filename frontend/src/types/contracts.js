/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,result:Object,approved:boolean}} AnalysisJob */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean}} ReportSchedule */
/** @typedef {{id:number,team:string,from_line:string,to_line:string,job_id:number,status:string,basis:Object,reverse_of:number|null,reverse_order_id:number|null}} LineOrder */
/** @typedef {{id:number,order_id:number,side:'from'|'to',receipt_id:string,line:string,actor:string,recorded_at:number}} LineHandover */
/** @typedef {{team:string,current_line:string,pending_order:LineOrder|null,effective_order:LineOrder|null}} LineBoard */
export {};
