"""Product catalog management over durable workspace records."""
import json, math, re
from .db import connect
from .workflows import _record, TRANSITIONS

def list_products(path, query="", status=""):
    if not isinstance(query,str) or len(query)>200: raise ValueError("search query is too long")
    if status and status not in {"draft","research","approved","archived"}:
        raise ValueError("invalid product status")
    sql="SELECT * FROM workspace_records WHERE kind='product'"
    args=[]
    if query.strip():
        sql+=" AND (title LIKE ? OR data_json LIKE ?)"
        term="%"+query.strip().replace("%","\\%").replace("_","\\_")+"%"
        args.extend([term,term])
    if status:
        sql+=" AND status=?";args.append(status)
    sql+=" ORDER BY updated_at DESC,id DESC LIMIT 250"
    with connect(path) as conn:
        return [_record(row) for row in conn.execute(sql,args).fetchall()]

def update_product(path, product_id, changes):
    if isinstance(product_id,bool) or not isinstance(product_id,int) or product_id<1:
        raise ValueError("invalid product id")
    if not isinstance(changes,dict) or not changes:
        raise ValueError("provide at least one field to update")
    allowed={"title","status","selling_price","currency","description","vendor","product_type","tags","sku","model","cost","notes"}
    unknown=set(changes)-allowed
    if unknown: raise ValueError("unsupported fields: "+", ".join(sorted(unknown)))
    with connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row=conn.execute("SELECT * FROM workspace_records WHERE id=? AND kind='product'",(product_id,)).fetchone()
        if row is None: raise ValueError("product not found")
        title=row["title"]
        if "title" in changes:
            value=changes["title"]
            if not isinstance(value,str) or not value.strip() or len(value.strip())>200:
                raise ValueError("title must be 1-200 characters")
            title=value.strip()
        data=json.loads(row["data_json"])
        for key in ("selling_price","cost"):
            if key in changes:
                value=changes[key]
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                    raise ValueError(key+" must be a finite non-negative number")
                data[key]=round(float(value),2)
        if "currency" in changes:
            value=changes["currency"]
            if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z]{3}",value):
                raise ValueError("currency must be a three-letter code")
            data["currency"]=value.upper()
        if "tags" in changes:
            value=changes["tags"]
            if not isinstance(value,list) or len(value)>30 or any(not isinstance(x,str) or not x.strip() or len(x)>80 for x in value):
                raise ValueError("tags must be up to 30 non-empty strings of at most 80 characters")
            data["tags"]=[x.strip() for x in value]
        for key in ("description","vendor","product_type","sku","model","notes"):
            if key in changes:
                value=changes[key]
                if not isinstance(value,str) or len(value)>2000:
                    raise ValueError(key+" must be text of at most 2000 characters")
                data[key]=value.strip()
        status=row["status"]
        if "status" in changes:
            target=changes["status"]
            if target not in TRANSITIONS["product"].get(status,set()):
                raise ValueError("invalid product status transition from "+status+" to "+str(target))
            status=target
        conn.execute("UPDATE workspace_records SET title=?,status=?,data_json=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                     (title,status,json.dumps(data,ensure_ascii=False,separators=(",",":"),sort_keys=True),product_id))
        conn.execute("INSERT INTO events(topic,entity_type,entity_id,data_json) VALUES(?,?,?,?)",
                     ("product.updated","product",str(product_id),json.dumps({"fields":sorted(changes)},separators=(",",":"))))
        return _record(conn.execute("SELECT * FROM workspace_records WHERE id=?",(product_id,)).fetchone())
