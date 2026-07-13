
const BASE = import.meta.env.VITE_API_BASE_URL;

async function request(path, options={})
{

    const res = await fetch(`${BASE}${path}`, {
        ...options,
        credentials: "include",
        headers: {"Content-Type" : "application/json", ...options.headers },

    });
    const body = await res.json().catch(() => null);
    if(!res.ok)
    {
        const err = new Error(body?.message || "Request failed");
        err.status = res.status;
        throw err;
    }
    return body;
}


export const authApi = {
    loginWithGoogle: (idToken) =>
        request("accounts/google/login/", {method: "POST", body: JSON.stringify({id_token : idToken}) }),
    getCurrentUser: () => request("accounts/me/", {method: "GET"}),
    refreshToken: () => request("accounts/token/refresh/", {method: "POST"}),
    logout: () => request("accounts/logout/", { method: "POST"}),
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