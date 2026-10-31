"""Read-only real-mouse diagnosis of successive other-student placements."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from plan_e2e import load_test_week, clear_calendar


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width":1800,"height":1200}, locale="fa-IR")
        page.on('dialog', lambda d: d.accept())
        page.goto(os.environ.get('PLAN_BASE_URL','https://panel.kimiagarkhoone.com')+'/login/',wait_until='domcontentloaded')
        page.fill('#username',os.environ.get('PLAN_USERNAME') or 'admin')
        page.fill('#password',os.environ['PLAN_PASSWORD'])
        page.click('form button[type="submit"]')
        page.wait_for_url('**/plan/')
        load_test_week(page)
        page.wait_for_load_state('networkidle')
        clear_calendar(page)
        source = page.evaluate("""() => Array.from(document.querySelector('#otherStudentSelect').options).find(o=>o.text.includes('الزهرا') && o.text.includes('تجربی'))?.value""")
        if not source: raise AssertionError('Requested Alzahra experimental source was not found')
        page.select_option('#otherStudentSelect',value=source)
        page.wait_for_function("window.jQuery('#otherStudentTasks > .other-plan-task').length >= 4")
        page.wait_for_load_state('networkidle')
        page.evaluate("""() => {
          window.__reuseDrops=[];
          window.jQuery('.calendar .task-container').each(function(){
            const inst=window.jQuery(this).droppable('instance'), previous=inst.options.drop;
            const wrapped=function(e,ui){
              const data=ui.draggable.data();
              const result=previous.call(this,e,ui);
              window.__reuseDrops.push({source:data.source_detail_id, attr:ui.draggable.attr('data-source-detail-id'),
                used:window.jQuery('.calendar-task[data-source-detail-id]').map(function(){return this.getAttribute('data-source-detail-id')}).get(),
                visible:ui.draggable.is(':visible'), result:result});
              return result;
            };
            wrapped.planRealInteraction=true; inst.options.drop=wrapped;
          });
        }""")
        records=[]
        for index in range(4):
            card=page.locator('#otherStudentTasks > .other-plan-task:visible').first
            card.scroll_into_view_if_needed()
            origin=card.get_attribute('data-source-detail-id')
            before=page.locator('#otherStudentTasks > .other-plan-task:visible').count()
            box=card.bounding_box()
            target=page.locator('.calendar .day-column').nth(index).locator('.task-container').bounding_box()
            page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
            page.mouse.down()
            page.mouse.move(box['x']+box['width']/2+10,box['y']+box['height']/2+3,steps=4)
            page.mouse.move(target['x']+target['width']/2,target['y']+100,steps=24)
            page.mouse.up()
            page.wait_for_timeout(400)
            record=page.evaluate("""({origin,before}) => ({origin,before,
              after:window.jQuery('#otherStudentTasks > .other-plan-task:visible').length,
              placed:window.jQuery('.calendar-task[data-source-detail-id]').filter(function(){return this.getAttribute('data-source-detail-id')===origin}).length,
              drops:window.__reuseDrops.slice(-1),
              origins:window.jQuery('#otherStudentTasks > .other-plan-task').map(function(){return {attr:this.getAttribute('data-source-detail-id'),raw:window.jQuery(this).data('source_detail_id'),visible:window.jQuery(this).is(':visible'),dragging:this.classList.contains('ui-draggable-dragging')}}).get()
            })""",{'origin':origin,'before':before})
            print('REUSE_SEQUENCE',json.dumps(record,ensure_ascii=False),flush=True)
            records.append(record)
        page.screenshot(path='plan-reuse-sequence.png',full_page=False)
        Path('plan-reuse-sequence.json').write_text(json.dumps(records,ensure_ascii=False))
        if os.environ.get('PLAN_REUSE_ASSERT') == '1':
            assert all(r['placed']==1 and r['after']==r['before']-1 for r in records), 'Every sequential mouse drop must consume precisely its source'
        browser.close()

if __name__=='__main__': main()
