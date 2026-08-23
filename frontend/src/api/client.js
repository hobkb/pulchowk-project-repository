
const BASE = import.meta.env.VITE_API_BASE_URL;
const REFRESH_PATH = "accounts/token/refresh/";

// Called once the shared token refresh itself fails, so the app can react
// (e.g. redirect to sign-in) instead of leaving a caller stuck on a page
// that will keep 401ing. Wired up by AuthContext.
let onSessionExpired = null;
export function setOnSessionExpired(callback) {
    onSessionExpired = callback;
}

// A single in-flight refresh, shared by every caller that hits a 401 at
// the same time. Without this, concurrent requests each independently
// racing to refresh the token is exactly how a refresh/retry loop starts;
// with it, everyone awaits the same attempt and only one refresh call is
// ever made per expiry.
let refreshInFlight = null;
function refreshAccessTokenOnce() {
    if (!refreshInFlight) {
        refreshInFlight = authApi
            .refreshToken()
            .then(() => true)
            .catch(() => false)
            .finally(() => {
                refreshInFlight = null;
            });
    }
    return refreshInFlight;
}

async function request(path, options={}, isRetry=false)
{
    const isFormData = options.body instanceof FormData;
    const headers = isFormData
        ? { ...(options.headers || {}) }
        : { "Content-Type" : "application/json", ...(options.headers || {}) };

    const res = await fetch(`${BASE}${path}`, {
        ...options,
        credentials: "include",
        headers,
    });

    // On an expired access token, refresh (once, shared) and retry the
    // original request (once). The refresh endpoint itself is excluded to
    // avoid ever recursing into this branch from its own failure.
    if (res.status === 401 && !isRetry && path !== REFRESH_PATH) {
        const refreshed = await refreshAccessTokenOnce();
        if (refreshed) {
            return request(path, options, true);
        }
        onSessionExpired?.();
    }

    const body = await res.json().catch(() => null);
    if(!res.ok)
    {
        const errMessage = body?.message || (typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail || body?.errors || "Request failed"));
        const err = new Error(errMessage);
        err.status = res.status;
        err.data = body;
        throw err;
    }
    return body;
}


export const authApi = {
    loginWithGoogle: (idToken) =>
        request("accounts/google/login/", {method: "POST", body: JSON.stringify({id_token : idToken}) }),
    getFacultyList: () => request("accounts/faculty/", {method: "GET"}),
    completeProfile: (formData) =>
        request("accounts/profile/complete/", {method: "POST", body: JSON.stringify(formData)}),
    getDepartments: () => request("organization/departments/", {method: "GET"}),
    getCurrentUser: () => request("accounts/me/", {method: "GET"}),
    refreshToken: () => request("accounts/token/refresh/", {method: "POST"}),
    logout: () => request("accounts/logout/", { method: "POST"}),
};

export const projectsApi = {
    // Verified (Published) projects only — see docs/backend/actions.md.
    // `params` are all server-side: q (keyword search), department,
    // academic_level, batch. Filtering happens in the database, not here.
    list: (params = {}, options = {}) => {
        const qs = new URLSearchParams(
            Object.entries(params).filter(([, v]) => v != null && v !== "")
        ).toString();
        return request(`repository/projects/${qs ? `?${qs}` : ""}`, {method: "GET", ...options});
    },
    detail: (id, options = {}) => request(`repository/projects/${id}/`, {method: "GET", ...options}),
    // The filter values that actually occur among published projects,
    // with counts — so the browse filters offer nothing that matches zero
    // records.
    // Accepts the same filters as list(): each facet dimension is counted
    // with the OTHER active filters applied, so an option's count is what
    // selecting it will actually return.
    facets: (params = {}) => {
        const qs = new URLSearchParams(
            Object.entries(params).filter(([, v]) => v != null && v !== "")
        ).toString();
        return request(`repository/projects/facets/${qs ? `?${qs}` : ""}`, {method: "GET"});
    },
};

export const accessRequestsApi = {
    // In-app report access. There is no email in this flow: a request
    // notifies every reviewer, and an approval unlocks the PDF for the
    // requester immediately.
    request: (projectId, reason) =>
        request(`repository/projects/${projectId}/access-request/`, {
            method: "POST",
            body: JSON.stringify({ reason: reason || "" }),
        }),
    // Withdraw a request that has not been decided yet. The request and
    // the reviewers' notifications about it are both removed.
    cancel: (projectId) =>
        request(`repository/projects/${projectId}/access-request/cancel/`, {
            method: "DELETE",
        }),
    mine: () => request("repository/access-requests/mine/", { method: "GET" }),
    queue: (params = {}) => {
        const qs = new URLSearchParams(
            Object.entries(params).filter(([, v]) => v != null && v !== "")
        ).toString();
        return request(`repository/access-requests/${qs ? `?${qs}` : ""}`, { method: "GET" });
    },
    decide: (id, decision, note) =>
        request(`repository/access-requests/${id}/${decision}/`, {
            method: "POST",
            body: JSON.stringify({ note: note || "" }),
        }),
};

export const profileApi = {
    // The narrow set of fields the account holder owns. Identity -- email,
    // a roll number proven by that email, and the role -- is not editable
    // here and is rejected or ignored by the server.
    update: (data) =>
        request("accounts/profile/", { method: "PATCH", body: JSON.stringify(data) }),
};

export const roleRequestsApi = {
    // Faculty and administrator roles are granted, never self-assigned:
    // onboarding files a request here and an existing administrator
    // decides it. Every endpoint below is superuser-only server-side.
    queue: (params = {}) => {
        const qs = new URLSearchParams(
            Object.entries(params).filter(([, v]) => v != null && v !== "")
        ).toString();
        return request(`accounts/role-requests/${qs ? `?${qs}` : ""}`, { method: "GET" });
    },
    mine: () => request("accounts/role-requests/mine/", { method: "GET" }),
    decide: (id, decision) =>
        request(`accounts/role-requests/${id}/${decision}/`, { method: "POST" }),
};

export const projectAdminApi = {
    update: (projectId, data) =>
        request(`repository/projects/${projectId}/manage/`, {
            method: "PATCH",
            body: JSON.stringify(data),
        }),
    remove: (projectId) =>
        request(`repository/projects/${projectId}/manage/`, { method: "DELETE" }),
};

export const bookmarksApi = {
    // The signed-in user's saved projects. Scoped to the requesting user
    // by the backend; there is no way to read anyone else's.
    list: (params = {}) => {
        const qs = new URLSearchParams(
            Object.entries(params).filter(([, v]) => v != null && v !== "")
        ).toString();
        return request(`repository/bookmarks/${qs ? `?${qs}` : ""}`, {method: "GET"});
    },
    status: (projectId) => request(`repository/bookmarks/${projectId}/`, {method: "GET"}),
    add: (projectId) =>
        request("repository/bookmarks/", {method: "POST", body: JSON.stringify({project: projectId})}),
    remove: (projectId) => request(`repository/bookmarks/${projectId}/`, {method: "DELETE"}),
};

export const notificationsApi = {
    list: (params = {}) => {
        const qs = new URLSearchParams(
            Object.entries(params).filter(([, v]) => v != null && v !== "")
        ).toString();
        return request(`notifications/${qs ? `?${qs}` : ""}`, {method: "GET"});
    },
    unreadCount: () => request("notifications/unread-count/", {method: "GET"}),
    markRead: (id) => request(`notifications/${id}/read/`, {method: "POST"}),
    markAllRead: () => request("notifications/read-all/", {method: "POST"}),
};

export const ingestionApi = {
    // Uploads via XHR rather than fetch purely so the browser's real
    // upload-progress events are available. The percentage reported is the
    // genuine share of bytes written to the socket -- not a simulated
    // timer -- so the indicator only moves when data actually moves.
    uploadJob: (formData, { onProgress } = {}) =>
        new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("POST", `${BASE}ingestion/jobs/`);
            xhr.withCredentials = true;

            if (onProgress) {
                xhr.upload.onprogress = (event) => {
                    if (event.lengthComputable) {
                        onProgress(Math.round((event.loaded / event.total) * 100));
                    }
                };
                // Once the last byte is sent the server is working; report
                // that as complete-upload rather than leaving it at 99%.
                xhr.upload.onload = () => onProgress(100);
            }

            xhr.onload = () => {
                let body = null;
                try {
                    body = JSON.parse(xhr.responseText);
                } catch {
                    body = null;
                }
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(body);
                    return;
                }
                const message =
                    body?.message ||
                    (typeof body?.detail === "string" ? body.detail : null) ||
                    `Upload failed (${xhr.status}).`;
                const error = new Error(message);
                error.status = xhr.status;
                error.data = body;
                reject(error);
            };
            xhr.onerror = () => reject(new Error("The upload could not reach the server."));
            xhr.onabort = () => reject(new Error("The upload was cancelled."));
            xhr.send(formData);
        }),
    listJobs: (params = {}) => {
        const qs = new URLSearchParams(
            Object.entries(params).filter(([, v]) => v != null && v !== "")
        ).toString();
        return request(`ingestion/jobs/${qs ? `?${qs}` : ""}`, { method: "GET" });
    },
    getJob: (id) => request(`ingestion/jobs/${id}/`, { method: "GET" }),
    patchJobPayload: (id, payload) => request(`ingestion/jobs/${id}/`, { method: "PATCH", body: JSON.stringify(payload) }),
    getJobLogs: (id) => request(`ingestion/jobs/${id}/logs/`, { method: "GET" }),
    publishJob: (id) => request(`ingestion/jobs/${id}/publish/`, { method: "POST" }),
};

export const metadataApi = {
    getChoices: () => request("repository/projects/choices/", { method: "GET" }),
};

export const organizationApi = {
    getDepartments: () => request("organization/departments/", { method: "GET" }),
    getCampuses: () => request("organization/campuses/", { method: "GET" }),
    getResearchGroups: (params = {}) => {
        const qs = new URLSearchParams(
            Object.entries(params).filter(([, v]) => v != null && v !== "")
        ).toString();
        return request(`organization/research-groups/${qs ? `?${qs}` : ""}`, { method: "GET" });
    },
};

export const accountsApi = {
    getFacultyList: () => request("accounts/faculty/", { method: "GET" }),
    createFaculty: (data) => request("accounts/faculty/create/", { method: "POST", body: JSON.stringify(data) }),
    getStudents: (params = {}) => {
        const qs = new URLSearchParams(
            Object.entries(params).filter(([, v]) => v != null && v !== "")
        ).toString();
        return request(`accounts/students/${qs ? `?${qs}` : ""}`, { method: "GET" });
    },
};



// Expired-access-token recovery (refresh + single retry) is handled
// generically inside request() now, so this is a thin, stable entry point
// kept for AuthContext — a second independent retry path here would race
// the shared one in request() instead of preventing that race.
export async function getCurrentUserWithRefresh()
{
    return await authApi.getCurrentUser();
}