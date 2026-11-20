import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
def line_order_dict(o):
    return {k:getattr(o,k) for k in ['id','team','from_line','to_line','job_id','status','basis','note','created_by','created_at','effective_at','closed_at','cancel_reason','cancelled_by','cancelled_at','reverse_of','reverse_order_id']}
def line_handover_dict(h):
    return {k:getattr(h,k) for k in ['id','order_id','side','receipt_id','line','actor','note','occurred_at','recorded_at']}
