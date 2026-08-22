
const BASE = import.meta.env.VITE_API_BASE_URL;

async function request(path, options={})
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
    // Verified (Published) projects only — see docs/backend/actions.md
    list: (params = {}) => {
        const qs = new URLSearchParams(
            Object.entries(params).filter(([, v]) => v != null && v !== "")
        ).toString();
        return request(`repository/projects/${qs ? `?${qs}` : ""}`, {method: "GET"});
    },
    detail: (id) => request(`repository/projects/${id}/`, {method: "GET"}),
};

export const ingestionApi = {
    uploadJob: (formData) => request("ingestion/jobs/", { method: "POST", body: formData }),
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



// when access token is expired refresh token API is called
export async function getCurrentUserWithRefresh()
{
    try{
        return await authApi.getCurrentUser();
    }
    catch(err)
    {
        if(err.status !=401) throw err;
        await authApi.refreshToken();
        return await authApi.getCurrentUser();
    }
}