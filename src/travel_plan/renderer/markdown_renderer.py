class MarkdownRenderer:
    def render(self,plan):
        lines=[f"# {plan.trip_id} 智能旅行计划","","## 行程总览",f"- 天数：{len(plan.days)}",f"- 住宿段：{len(plan.hotels)}",f"- 预算估算：¥{plan.budget.total:.2f}"]
        for day in plan.days:
            lines += ["",f"## 第 {day.day} 天 · {day.theme}"]
            for n in day.nodes:
                lines.append(f"- **{n.start_time}-{n.end_time}** {n.name}（{n.type}）")
                if n.transport_mode:lines.append(f"  - 交通：{n.transport_mode}，{n.distance_km:.1f} km，约 {n.duration_min} 分钟")
                if n.type in {"lunch","dinner"}:lines.append(f"  - 餐饮：{n.metadata.get('cuisine')}，人均 ¥{n.metadata.get('price_per_person')}，绕路 {n.metadata.get('detour_min')} 分钟")
        d=plan.hotel_decision;lines += ["","## 住宿",f"- {d.get('action')}：{d.get('reason')}（净收益 {d.get('net_gain_min')} 分钟）","","## 预约提醒"]
        reminders=[n for day in plan.days for n in day.nodes if n.metadata.get("reservation_required") or n.metadata.get("latest_entry_time")]
        lines.extend([f"- {n.name}：预约={n.metadata.get('reservation_required')}，最晚入场={n.metadata.get('latest_entry_time')}" for n in reminders] or ["- 无"])
        b=plan.budget;lines += ["","## 费用",f"- 门票 ¥{b.tickets:.2f} / 餐饮 ¥{b.meals:.2f} / 住宿 ¥{b.hotels:.2f} / 交通 ¥{b.transport:.2f}",f"- **总计 ¥{b.total:.2f}**","","## 风险",f"- 天气：以 mock/配置的预报为依据",f"- Review 剩余问题：{len(plan.remaining_issues)}"]
        return "\n".join(lines)

