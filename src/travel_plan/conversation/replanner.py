from copy import deepcopy

class Replanner:
    def apply(self,scope,old,new,day=None,meal=None,locked_items=()):
        if scope=="GLOBAL":
            for locked in locked_items:
                number=int(locked.removeprefix("DAY:")); replacement=next((d for d in new.days if d.day==number),None); original=next((d for d in old.days if d.day==number),None)
                if replacement and original:new.days[new.days.index(replacement)]=deepcopy(original)
            return new
        result=deepcopy(old)
        if f"DAY:{day}" in locked_items:return result
        old_day=next(d for d in result.days if d.day==day);new_day=next(d for d in new.days if d.day==day)
        if scope=="DAY":old_day.nodes=deepcopy(new_day.nodes);old_day.theme=new_day.theme;old_day.route_score=new_day.route_score
        elif scope=="NODE":
            old_attr=[i for i,n in enumerate(old_day.nodes) if n.type=="attraction"]
            new_attr=[n for n in new_day.nodes if n.type=="attraction"]
            if old_attr and new_attr:old_day.nodes[old_attr[-1]]=deepcopy(new_attr[-1])
        elif scope=="MEAL":
            replacement=next((n for n in new_day.nodes if n.type==meal),None)
            if replacement:
                pos=next((i for i,n in enumerate(old_day.nodes) if n.type==meal),len(old_day.nodes))
                if pos<len(old_day.nodes):old_day.nodes[pos]=deepcopy(replacement)
                else:old_day.nodes.append(deepcopy(replacement));old_day.nodes.sort(key=lambda n:n.start_time)
        return result

