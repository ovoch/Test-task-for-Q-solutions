import os
import shutil
from playwright.sync_api import sync_playwright

PATH_TO_VIDEO_FOLDER = "./video"
_ACTIVE_PAGE = None


def hide_automation(context):
    js_script = """
    (() => {
        try { delete Object.getPrototypeOf(navigator).webdriver; } catch (e) {}
        try { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); } catch (e) {}
        try { Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] }); } catch (e) {}
        try { if (!window.chrome) window.chrome = { runtime: {} }; } catch (e) {}

        const spoofGL = (proto) => {
            if (!proto) return;
            const orig = proto.getParameter;
            proto.getParameter = function(param) {
                if (param === 37445) return 'Intel Inc.';
                if (param === 37446) return 'Intel(R) Iris(R) Xe Graphics';
                return orig.apply(this, [param]);
            };
        };
        try {
            spoofGL(WebGLRenderingContext.prototype);
            if (typeof WebGL2RenderingContext !== 'undefined') {
                spoofGL(WebGL2RenderingContext.prototype);
            }
        } catch (e) {}
    })();
    """
    context.add_init_script(script=js_script)


def mouse_ui_overlay(context):
    js_script = """
    (() => {
        if (window.top !== window) return;

        let mouseX = 0;
        let mouseY = 0;
        try {
            mouseX = Number(sessionStorage.getItem('__mx__') || 0);
            mouseY = Number(sessionStorage.getItem('__my__') || 0);
        } catch (e) {}

        function placeCursor() {
            const glow = document.getElementById('__mouse_glow__');
            const arrow = document.getElementById('__mouse_arrow__');
            if (glow) {
                glow.style.left = `${mouseX}px`;
                glow.style.top = `${mouseY}px`;
            }
            if (arrow) {
                arrow.style.left = `${mouseX}px`;
                arrow.style.top = `${mouseY}px`;
            }
        }

        function initCursor() {
            if (!document.body || document.getElementById('__mouse_glow__')) return;

            const glow = document.createElement('div');
            glow.id = '__mouse_glow__';
            Object.assign(glow.style, {
                position: 'fixed',
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                backgroundColor: 'rgba(255, 230, 0, 0.45)',
                pointerEvents: 'none',
                zIndex: '2147483645',
                transform: 'translate(-50%, -50%)'
            });

            const NS = 'http://www.w3.org/2000/svg';
            const arrow = document.createElementNS(NS, 'svg');
            arrow.id = '__mouse_arrow__';
            arrow.setAttribute('width', '32');
            arrow.setAttribute('height', '32');
            arrow.setAttribute('viewBox', '0 0 32 32');
            Object.assign(arrow.style, {
                position: 'fixed',
                pointerEvents: 'none',
                zIndex: '2147483647'
            });
            const path = document.createElementNS(NS, 'path');
            path.setAttribute('d', 'M2 2 L2 25 L8 19.5 L12.5 29.5 L17 27.5 L12.5 17.5 L21 17.5 Z');
            path.setAttribute('fill', 'white');
            path.setAttribute('stroke', 'black');
            path.setAttribute('stroke-width', '2');
            path.setAttribute('stroke-linejoin', 'round');
            arrow.appendChild(path);

            document.body.appendChild(glow);
            document.body.appendChild(arrow);
            placeCursor();
        }

        window.addEventListener('mousemove', (e) => {
            mouseX = e.clientX;
            mouseY = e.clientY;
            try {
                sessionStorage.setItem('__mx__', mouseX);
                sessionStorage.setItem('__my__', mouseY);
            } catch (err) {}
            initCursor();
            placeCursor();
        }, true);

        window.addEventListener('mousedown', (e) => {
            if (!document.body) return;
            const rip = document.createElement('div');
            Object.assign(rip.style, {
                position: 'fixed',
                left: `${e.clientX}px`,
                top: `${e.clientY}px`,
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: 'rgba(255, 0, 0, 0.35)',
                border: '2px solid red',
                boxSizing: 'border-box',
                pointerEvents: 'none',
                zIndex: '2147483646',
                transform: 'translate(-50%, -50%) scale(1)',
                opacity: '1',
                transition: 'transform 0.5s ease-out, opacity 0.5s ease-out'
            });
            document.body.appendChild(rip);
            setTimeout(() => {
                rip.style.transform = 'translate(-50%, -50%) scale(4)';
                rip.style.opacity = '0';
            }, 20);
            setTimeout(() => rip.remove(), 600);
        }, true);

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initCursor);
        } else {
            initCursor();
        }
        setInterval(initCursor, 300);
    })();
    """
    context.add_init_script(script=js_script)


def ShowCallout(text, bgColor="yellow", textColor="black", fade=True):
    if not _ACTIVE_PAGE:
        return
    try:
        _ACTIVE_PAGE.evaluate(
            """([text, bgColor, textColor, fade]) => {
                if (!document.body) return;
                const old = document.getElementById('__callout__');
                if (old) old.remove();
                const box = document.createElement('div');
                box.id = '__callout__';
                box.textContent = text;
                Object.assign(box.style, {
                    position: 'fixed',
                    bottom: '30px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    whiteSpace: 'nowrap',
                    backgroundColor: bgColor,
                    color: textColor,
                    fontSize: '16pt',
                    fontFamily: 'Arial, sans-serif',
                    padding: '8px 16px',
                    border: '1px solid black',
                    borderRadius: '4px',
                    zIndex: '2147483644',
                    pointerEvents: 'none',
                    opacity: fade ? '0' : '1',
                    transition: fade ? 'opacity 2s ease' : 'none'
                });
                document.body.appendChild(box);
                if (fade) {
                    setTimeout(() => { box.style.opacity = '1'; }, 50);
                    setTimeout(() => { box.style.opacity = '0'; }, 3000);
                    setTimeout(() => { box.remove(); }, 5200);
                }
            }""",
            [text, bgColor, textColor, fade],
        )
    except Exception:
        pass


def handle_page(page):
    page.wait_for_load_state()


def get_user_agent(browser):
    temp_context = browser.new_context()
    temp_page = temp_context.new_page()
    user_agent = temp_page.evaluate("navigator.userAgent")
    temp_context.close()
    return user_agent.replace("HeadlessChrome", "Chrome")


def drag_cursor_to_searchbox(page):
    page.wait_for_selector('textarea[name="q"]', timeout=30000)
    searchbox = page.locator('textarea[name="q"]').bounding_box()
    page.mouse.move(searchbox["x"] + 20, searchbox["y"] + 15, steps = 50)
    page.mouse.click(searchbox["x"] + 20, searchbox["y"] + 15, button = "left")


def keyboard_input(page, company_name, city):
    ShowCallout(f"Searching in {city}", "yellow", "black", True)
    page.keyboard.type(f"Magento developer in {city}", delay = 100)


def drag_cursor_to_searchbutton(page):
    search_button = page.locator('button[aria-label="Search"]').bounding_box()
    page.mouse.move(search_button["x"] + 40, search_button["y"] + 10, steps = 75)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(2000)


def drag_cursor_to_first_result(page):
    handle_page(page)
    page.wait_for_selector('a[data-testid="result-title-a"]', timeout=45000)
    page.wait_for_timeout(500)
    first_result = page.locator('a[data-testid="result-title-a"]').first
    first_result_href = first_result.bounding_box()
    page.mouse.move(first_result_href["x"] + 30, first_result_href["y"] + 10, steps = 75)
    page.wait_for_timeout(500)
    page.mouse.click(first_result_href["x"] + 30, first_result_href["y"] + 10, button = "left")
    page.wait_for_timeout(300)


def CaptureVideo_Magento(
    url,
    company_name,
    language,
    country,
    postcode,
    city,
    street,
    house_no,
):
    global _ACTIVE_PAGE
    os.makedirs(PATH_TO_VIDEO_FOLDER, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            chromium = playwright.chromium
            launch_args = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            try:
                browser = chromium.launch(
                    headless=True,
                    channel="chromium",
                    args=launch_args,
                    ignore_default_args=["--enable-automation"],
                )
            except Exception:
                browser = chromium.launch(
                    headless=True,
                    args=launch_args,
                    ignore_default_args=["--enable-automation"],
                )

            context = browser.new_context(
                user_agent=get_user_agent(browser),
                locale="en-US",
                viewport={"width": 1280, "height": 720},
                record_video_dir=PATH_TO_VIDEO_FOLDER,
                record_video_size={"width": 1280, "height": 720},
            )

            hide_automation(context)
            mouse_ui_overlay(context)
            page = context.new_page()
            _ACTIVE_PAGE = page

            page.goto(url, timeout=60000)

            drag_cursor_to_searchbox(page)
            keyboard_input(page, company_name, city)
            drag_cursor_to_searchbutton(page)
            drag_cursor_to_first_result(page)

            temp_path = page.video.path()
            _ACTIVE_PAGE = None
            context.close()
            browser.close()

            safe_name = "".join(c if c.isalnum() or c in " -_." else "_" for c in company_name).strip()
            if not safe_name:
                safe_name = "video"
            final_path = os.path.abspath(os.path.join(PATH_TO_VIDEO_FOLDER, f"{safe_name}.webm"))
            if os.path.exists(final_path):
                os.remove(final_path)
            shutil.move(temp_path, final_path)
            return final_path

    except Exception as e:
        _ACTIVE_PAGE = None
        print(f"Error processing {company_name}: {e}")
        return None