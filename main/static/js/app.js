(() => {
    const jsonHeaders = {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json',
    };

    const loading = document.getElementById('loading-overlay');

    function showLoading() {
        loading?.classList.add('is-active');
    }

    function hideLoading() {
        loading?.classList.remove('is-active');
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    window.showToast = function showToast(message, type = 'success') {
        const area = document.getElementById('toast-area');
        if (!area || !window.bootstrap) {
            alert(message);
            return;
        }

        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        toast.innerHTML = `
            <div class="toast-header">
                <span class="toast-icon ${type === 'error' ? 'error' : ''} me-2">
                    <i class="fa-solid ${type === 'error' ? 'fa-xmark' : 'fa-check'}"></i>
                </span>
                <strong class="me-auto">SNS BBS</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="閉じる"></button>
            </div>
            <div class="toast-body">${escapeHtml(message)}</div>
        `;
        area.appendChild(toast);
        const instance = new bootstrap.Toast(toast, { delay: 2600 });
        toast.addEventListener('hidden.bs.toast', () => toast.remove());
        instance.show();
    };

    async function requestJson(url, options = {}) {
        showLoading();
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    ...jsonHeaders,
                    ...(options.headers || {}),
                },
            });
            const data = await response.json();
            if (!response.ok || data.ok === false) {
                throw new Error(data.message || '処理に失敗しました');
            }
            return data;
        } finally {
            hideLoading();
        }
    }

    function replyItem(reply) {
        return `
            <div class="reply-item row-fade-in">
                <strong>${escapeHtml(reply.username)}</strong>
                <p>${escapeHtml(reply.body)}</p>
                <span>${escapeHtml(reply.created_at)}</span>
            </div>
        `;
    }

    function entryCard(entry) {
        const replies = (entry.replies || []).map(replyItem).join('');
        return `
            <article class="post-card row-fade-in" data-entry-id="${entry.id}">
                <div class="post-main">
                    <div class="post-avatar"><i class="fa-solid fa-user"></i></div>
                    <div class="post-body">
                        <div class="post-head">
                            <strong>${escapeHtml(entry.name)}</strong>
                            <span>${escapeHtml(entry.date)}</span>
                        </div>
                        <p>${escapeHtml(entry.article)}</p>
                        <div class="post-actions">
                            <button class="action-button ${entry.liked_by_current_user ? 'is-active' : ''}" type="button" data-like-entry data-entry-id="${entry.id}">
                                <i class="fa-solid fa-heart"></i>
                                <span data-like-count>${entry.likes_count || 0}</span>
                            </button>
                            <button class="action-button" type="button" data-reply-toggle>
                                <i class="fa-solid fa-reply"></i>
                                <span>返信</span>
                            </button>
                            ${entry.can_delete ? `
                            <button class="action-button danger" type="button" data-delete-entry data-entry-id="${entry.id}">
                                <i class="fa-solid fa-trash"></i>
                                <span>削除</span>
                            </button>` : ''}
                        </div>
                    </div>
                </div>
                <div class="reply-panel">
                    <div class="reply-list" data-reply-list>${replies}</div>
                    <form class="reply-form p-0 border-0 shadow-none bg-transparent" data-reply-form data-entry-id="${entry.id}">
                        <input class="form-control" name="body" placeholder="返信を書く" required>
                        <button class="btn btn-primary btn-sm" type="submit">返信</button>
                    </form>
                </div>
            </article>
        `;
    }

    function setEntryEmptyState() {
        const list = document.getElementById('entry-list');
        const empty = document.getElementById('entry-empty');
        if (!list || !empty) return;
        empty.classList.toggle('d-none', list.children.length > 0);
    }

    function initEntryAjax() {
        const page = document.querySelector('[data-thread-page]');
        const form = document.getElementById('entry-form');
        const list = document.getElementById('entry-list');
        if (!page || !form || !list) return;

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            try {
                const data = await requestJson(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                });
                list.insertAdjacentHTML('beforeend', entryCard(data.entry));
                form.reset();
                setEntryEmptyState();
                window.showToast(data.message || '投稿しました');
            } catch (error) {
                window.showToast(error.message, 'error');
            }
        });

        const modalEl = document.getElementById('delete-entry-modal');
        const confirm = document.getElementById('delete-entry-confirm');
        const modal = modalEl && window.bootstrap ? new bootstrap.Modal(modalEl) : null;
        let deleteTargetId = null;

        document.addEventListener('click', async (event) => {
            const likeButton = event.target.closest('[data-like-entry]');
            if (likeButton) {
                try {
                    const data = await requestJson(`/entry/${likeButton.dataset.entryId}/like`, { method: 'POST' });
                    likeButton.classList.toggle('is-active', data.liked);
                    likeButton.querySelector('[data-like-count]').textContent = data.likes_count;
                    window.showToast(data.message);
                } catch (error) {
                    window.showToast(error.message, 'error');
                }
                return;
            }

            const replyToggle = event.target.closest('[data-reply-toggle]');
            if (replyToggle) {
                const card = replyToggle.closest('.post-card');
                card?.querySelector('.reply-form input')?.focus();
                return;
            }

            const deleteButton = event.target.closest('[data-delete-entry]');
            if (deleteButton) {
                deleteTargetId = deleteButton.dataset.entryId;
                if (modal) modal.show();
            }
        });

        document.addEventListener('submit', async (event) => {
            const replyForm = event.target.closest('[data-reply-form]');
            if (!replyForm) return;
            event.preventDefault();
            try {
                const data = await requestJson(`/entry/${replyForm.dataset.entryId}/reply`, {
                    method: 'POST',
                    body: new FormData(replyForm),
                });
                replyForm.closest('.reply-panel')?.querySelector('[data-reply-list]')?.insertAdjacentHTML('beforeend', replyItem(data.reply));
                replyForm.reset();
                window.showToast(data.message || '返信しました');
            } catch (error) {
                window.showToast(error.message, 'error');
            }
        });

        confirm?.addEventListener('click', async () => {
            if (!deleteTargetId) return;
            try {
                const data = await requestJson(`/delete_entry/${deleteTargetId}`, { method: 'POST' });
                document.querySelector(`.post-card[data-entry-id="${data.entry_id}"]`)?.remove();
                setEntryEmptyState();
                modal?.hide();
                window.showToast(data.message || '削除しました');
            } catch (error) {
                window.showToast(error.message, 'error');
            } finally {
                deleteTargetId = null;
            }
        });

        const search = document.getElementById('entry-search');
        const clear = document.getElementById('entry-search-clear');
        let searchTimer = null;

        async function runEntrySearch() {
            const params = new URLSearchParams({
                thread: page.dataset.threadName,
                q: search.value,
            });
            try {
                const data = await requestJson(`/entries/search?${params.toString()}`);
                list.innerHTML = data.entries.map(entryCard).join('');
                setEntryEmptyState();
                window.showToast(`${data.count}件の投稿を表示しました`);
            } catch (error) {
                window.showToast(error.message, 'error');
            }
        }

        search?.addEventListener('input', () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(runEntrySearch, 350);
        });

        clear?.addEventListener('click', () => {
            if (!search) return;
            search.value = '';
            runEntrySearch();
        });
    }

    function userCard(user) {
        let action = '<span class="muted-text">自分のアカウントです</span>';
        if (!user.is_current_user) {
            if (user.state_from_currentuser === 1) {
                action = `
                    <form class="p-0 border-0 shadow-none bg-transparent" method="POST" action="/follow_lift">
                        <input type="hidden" name="opponent_id" value="${user.id}">
                        <input class="btn btn-secondary btn-sm" type="submit" value="フォロー解除">
                    </form>
                `;
            } else {
                action = `
                    <form class="p-0 border-0 shadow-none bg-transparent" method="POST" action="/follow">
                        <input type="hidden" name="to_user_id" value="${user.id}">
                        <input class="btn btn-primary btn-sm" type="submit" value="フォロー">
                    </form>
                `;
            }
        }

        return `
            <article class="user-card row-fade-in">
                <div class="d-flex align-items-center gap-3 mb-3">
                    <img class="profile-image" src="${escapeHtml(user.picture_url)}" alt="${escapeHtml(user.username)}のアイコン">
                    <div>
                        <h3 class="h5 mb-1">${escapeHtml(user.username)}</h3>
                        <p class="muted-text mb-0">${escapeHtml(user.bio || 'プロフィール未設定')}</p>
                    </div>
                </div>
                ${user.skills ? `<p class="muted-text small">${escapeHtml(user.skills)}</p>` : ''}
                <div class="d-flex flex-wrap gap-2">
                    <a class="btn btn-secondary btn-sm" href="${escapeHtml(user.profile_url)}">プロフィール</a>
                    ${user.is_current_user ? '' : `<a class="btn btn-primary btn-sm" href="${escapeHtml(user.chat_url)}">DM</a>`}
                    ${action}
                </div>
            </article>
        `;
    }

    function initUserSearchAjax() {
        const form = document.getElementById('user-search-form');
        const results = document.getElementById('user-search-results');
        const empty = document.getElementById('user-search-empty');
        if (!form || !results || !empty) return;

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            try {
                const data = await requestJson(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                });
                results.innerHTML = data.users.map(userCard).join('');
                empty.textContent = data.count ? '' : 'ユーザーが見つかりませんでした。';
                empty.classList.toggle('d-none', data.count > 0);
                window.showToast(data.message || '検索しました');
            } catch (error) {
                window.showToast(error.message, 'error');
            }
        });
    }

    function chatMessage(chat) {
        return `
            <article class="message-card ${chat.mine ? 'mine' : ''} row-fade-in">
                <div class="avatar-mini"><i class="fa-solid fa-user"></i></div>
                <div>
                    <strong>${escapeHtml(chat.username)}</strong>
                    <p class="mb-2">${escapeHtml(chat.message)}</p>
                    <span class="message-meta">${escapeHtml(chat.time)}</span>
                </div>
            </article>
        `;
    }

    function initChatAjax() {
        const form = document.getElementById('chat-form');
        const list = document.getElementById('chat-list');
        if (!form || !list) return;

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            try {
                const data = await requestJson(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                });
                document.getElementById('chat-empty')?.remove();
                list.insertAdjacentHTML('beforeend', chatMessage(data.chat));
                form.reset();
                window.showToast(data.message || 'DMを送信しました');
            } catch (error) {
                window.showToast(error.message, 'error');
            }
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initEntryAjax();
        initUserSearchAjax();
        initChatAjax();
    });
})();
