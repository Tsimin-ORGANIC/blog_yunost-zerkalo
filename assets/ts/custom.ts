// 钇·锆·拾遗 —— Yunost Zerkalo · 档案室交互
// 1. 盖戳涟漪：点在档案卡 / 按钮上，盖出一圈血锈红方形印痕
// 2. 显影颗粒：点击处溅出几粒银盐噪点（旧胶片显影）
// 3. 传阅次数：把 localStorage 里的本机传阅记录盖在文章卡右上角

/** 锈红 / 纸灰 / 铁灰——颗粒只从档案室的颜料柜里取色 */
const PALETTE = ['#8B0000', '#C24141', '#D4C5B0', '#5A5D63', '#4E729E'];

declare global {
    interface Window {
        __zrCirculation?: Record<string, number>;
    }
}

function prefersReducedMotion(): boolean {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** 在被点击元素上盖一圈方形「戳痕」涟漪 */
function spawnStamp(host: HTMLElement, e: MouseEvent): void {
    const rect = host.getBoundingClientRect();
    const size = Math.min(Math.max(rect.width, rect.height) * 0.6, 180);
    const ripple = document.createElement('span');
    ripple.className = 'zr-stamp-ripple';
    ripple.style.width = ripple.style.height = `${size}px`;
    ripple.style.left = `${e.clientX - rect.left - size / 2}px`;
    ripple.style.top = `${e.clientY - rect.top - size / 2}px`;
    host.appendChild(ripple);
    ripple.addEventListener('animationend', () => ripple.remove());
}

/** 点击处溅出几粒显影颗粒（微微下坠，像胶片上的灰尘掉落） */
function spawnGrain(x: number, y: number): void {
    const count = 5;
    for (let i = 0; i < count; i++) {
        const dot = document.createElement('span');
        dot.className = 'zr-grain';
        const size = 2 + Math.random() * 3; // 颗粒比颜料点细
        dot.style.width = dot.style.height = `${size}px`;
        dot.style.left = `${x - size / 2}px`;
        dot.style.top = `${y - size / 2}px`;
        dot.style.background = PALETTE[Math.floor(Math.random() * PALETTE.length)];
        dot.style.opacity = '0.8';
        document.body.appendChild(dot);

        const angle = Math.random() * Math.PI * 2;
        const distance = 12 + Math.random() * 26;
        const dx = Math.cos(angle) * distance;
        const dy = Math.sin(angle) * distance + 6;

        dot.animate(
            [
                { transform: 'translate(0, 0) scale(1)', opacity: 0.8 },
                {
                    transform: `translate(${dx}px, ${dy}px) scale(0.3)`,
                    opacity: 0,
                },
            ],
            {
                duration: 380 + Math.random() * 220,
                easing: 'cubic-bezier(0.2, 0.7, 0.3, 1)',
            },
        ).addEventListener('finish', () => dot.remove());
    }
}

function setupClickEffects(): void {
    if (prefersReducedMotion()) return;

    document.addEventListener('click', (e: MouseEvent) => {
        const target = e.target as HTMLElement | null;
        if (!target) return;

        // 输入框里点击不打扰
        if (target.closest('input, textarea')) return;

        // 盖戳：卡片和按钮
        const host = target.closest<HTMLElement>('.article-list article, button');
        if (host) spawnStamp(host, e);

        // 显影颗粒
        spawnGrain(e.clientX, e.clientY);
    });
}

/** 传阅次数：本机访问计数（localStorage，无需后端）
 *  文章页：显示本篇传阅次数；列表页卡片：显示总传阅次数
 *  挂到 .zr-circulation 元素上（由布局覆盖注入），没有挂点就不显示 */
function setupCirculationCounter(): void {
    try {
        const KEY = 'zr-circulation';
        const raw = localStorage.getItem(KEY);
        const data: Record<string, number> = raw ? JSON.parse(raw) : {};
        const path = window.location.pathname;
        data[path] = (data[path] || 0) + 1;
        // 防止无限增长：最多记 200 条路径
        const keys = Object.keys(data);
        if (keys.length > 200) {
            for (const k of keys.slice(0, keys.length - 200)) delete data[k];
        }
        localStorage.setItem(KEY, JSON.stringify(data));
        window.__zrCirculation = data;

        const total = Object.values(data).reduce((a, b) => a + b, 0);

        const mount = (el: HTMLElement, n: number) => {
            el.textContent = `传阅 ${n} 次`;
        };

        // 文章页（single 模板注入的挂点）
        document
            .querySelectorAll<HTMLElement>('.zr-circulation[data-mode="page"]')
            .forEach((el) => mount(el, data[path] || 1));

        // 列表页卡片（每张卡挂点带 data-path）
        document
            .querySelectorAll<HTMLElement>('.zr-circulation[data-mode="card"]')
            .forEach((el) => {
                const p = el.dataset.path || path;
                mount(el, data[p] || 0);
            });

        // 无挂点时的兜底：文章详情页的元信息行尾追加
        const inlineMeta = document.querySelector('.main-article .article-meta .inline-meta');
        if (inlineMeta && !document.querySelector('.zr-circulation')) {
            const span = document.createElement('span');
            span.className = 'zr-circulation';
            span.dataset.mode = 'page';
            inlineMeta.appendChild(span);
            mount(span, data[path] || 1);
        }

        // 首页右上角（库房总传阅）——不强制，有挂点才显示
        const headerBadge = document.querySelector<HTMLElement>('.zr-circulation[data-mode="total"]');
        if (headerBadge) mount(headerBadge, total);
    } catch {
        /* localStorage 不可用（隐私模式等）：静默降级，不影响阅读 */
    }
}

/** 案卷标签配色：锆蓝 / 丹砂红二选一，按标签名哈希决定——
 *  同一个标签全站固定同色（纯前端确定性「随机」，无闪烁）。
 *  分类章（.zr-file-tab）不参与，保持锆蓝。 */
function paintTagChips(): void {
    document.querySelectorAll<HTMLElement>('.article-tags a').forEach((el) => {
        const name = (el.textContent || '').trim();
        let hash = 5381;
        for (let i = 0; i < name.length; i++) {
            hash = (((hash << 5) + hash + name.charCodeAt(i)) | 0);
        }
        if (Math.abs(hash) % 2 === 1) {
            el.classList.add('zr-tag--cinnabar');
        }
    });
}

window.addEventListener('load', () => {
    setTimeout(setupClickEffects, 0);
    paintTagChips();
    setupCirculationCounter();
});

export {};
