// Sign-in (spec §7: Clerk). VITE_AUTH_MODE=dev skips sign-in for local work,
// matching the API's AUTH_MODE=dev (which the API refuses in production).
import { ClerkProvider, Show, SignIn, UserButton, useAuth } from "@clerk/react";
import { createContext, useContext, type ReactNode } from "react";

type Auth = { getToken: () => Promise<string | null>; userButton: ReactNode };
const AuthContext = createContext<Auth>({ getToken: async () => null, userButton: null });
export const useAuthToken = () => useContext(AuthContext);

export const DEV_AUTH = import.meta.env.VITE_AUTH_MODE === "dev";

function ClerkBridge({ children }: { children: ReactNode }) {
  const { getToken } = useAuth();
  return (
    <AuthContext.Provider value={{ getToken: () => getToken(), userButton: <UserButton /> }}>{children}</AuthContext.Provider>
  );
}

export function AuthGate({ children }: { children: ReactNode }) {
  if (DEV_AUTH) {
    return (
      <AuthContext.Provider value={{ getToken: async () => null, userButton: <span className="badge">dev sign-in</span> }}>
        {children}
      </AuthContext.Provider>
    );
  }
  const key = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
  if (!key) return <p className="page-message">Set VITE_CLERK_PUBLISHABLE_KEY (or VITE_AUTH_MODE=dev for local work).</p>;
  return (
    <ClerkProvider publishableKey={key}>
      <Show when="signed-out">
        <div className="page-message">
          <SignIn />
        </div>
      </Show>
      <Show when="signed-in">
        <ClerkBridge>{children}</ClerkBridge>
      </Show>
    </ClerkProvider>
  );
}
