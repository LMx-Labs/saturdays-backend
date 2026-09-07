import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { authApi } from "../api/modules/auth";
import { intendedRoute } from "../app/routing";
import { useAuth } from "../auth/AuthProvider";
import { useToast } from "../components/toastContext";
import { validateEmail, validatePassword } from "../components/formValidation";
import { Card, PageHeader, SmartForm } from "../components/ui";

type PublicAuthMode = "login" | "register" | "forgot" | "reset" | "verify" | "resend" | "invitation";

const copy: Record<PublicAuthMode, { eyebrow: string; title: string; submit: string }> = {
  login: { eyebrow: "Welcome back", title: "Sign in to continue", submit: "Sign in" },
  register: { eyebrow: "Join Saturdays", title: "Create your customer account", submit: "Create account" },
  forgot: { eyebrow: "Account recovery", title: "Reset your password", submit: "Send reset link" },
  reset: { eyebrow: "Account recovery", title: "Choose a new password", submit: "Reset password" },
  verify: { eyebrow: "Email verification", title: "Verify your email", submit: "Verify email" },
  resend: { eyebrow: "Email verification", title: "Request another verification", submit: "Resend email" },
  invitation: { eyebrow: "Staff invitation", title: "Accept your invitation", submit: "Accept invitation" },
};

export function AuthFlowPage({ mode }: { mode: PublicAuthMode }) {
  const { login, registerCustomer, acceptInvitation } = useAuth();
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { notify } = useToast();
  const token = params.get("token") || "";
  const mutation = useMutation({
    mutationFn: async (values: Record<string, unknown>) => {
      const email = String(values.email || "");
      const password = String(values.password || "");
      if (["login", "register", "forgot", "resend"].includes(mode)) {
        const error = validateEmail(email);
        if (error) throw new Error(error);
      }
      if (["register", "reset", "invitation"].includes(mode)) {
        const error = validatePassword(password);
        if (error) throw new Error(error);
      }
      if (mode === "login") return login(email, password);
      if (mode === "register") return registerCustomer(email, password);
      if (mode === "forgot") return authApi.forgotPassword(email);
      if (mode === "reset") return authApi.resetPassword(token, password);
      if (mode === "verify") return authApi.verifyEmail(token);
      if (mode === "resend") return authApi.resendVerification(email);
      return acceptInvitation(token, password);
    },
    onSuccess: (result) => {
      if ("role" in result) navigate(intendedRoute(location.state, result.role), { replace: true });
      else {
        notify(result.message);
        navigate("/auth/login", { replace: true });
      }
    },
  });
  const fields = mode === "verify"
    ? []
    : mode === "login" || mode === "register"
    ? [{ name: "email", label: "Email", type: "email" as const, required: true }, { name: "password", label: "Password", type: "password" as const, required: true }]
    : mode === "forgot" || mode === "resend"
      ? [{ name: "email", label: "Email", type: "email" as const, required: true }]
      : [{ name: "password", label: "New password", type: "password" as const, required: true }];
  const needsToken = ["reset", "verify", "invitation"].includes(mode);

  return (
    <Card className="auth-card">
      <span className="product-eyebrow">{copy[mode].eyebrow}</span>
      <h1>{copy[mode].title}</h1>
      {mode === "register" && <p>Public registration creates Customer accounts only. Staff access requires an invitation.</p>}
      {needsToken && !token ? <div className="inline-error">This link is missing its secure token.</div> : (
        <SmartForm fields={fields} submitLabel={copy[mode].submit} busy={mutation.isPending} error={mutation.error} onSubmit={(values) => mutation.mutate(values)} />
      )}
      <div className="auth-links">
        {mode !== "login" && <Link to="/auth/login">Back to sign in</Link>}
        {mode === "login" && <><Link to="/auth/register">Create customer account</Link><Link to="/auth/forgot-password">Forgot password?</Link><Link to="/auth/resend-verification">Resend verification</Link></>}
      </div>
    </Card>
  );
}

export function SecurityPage() {
  const { logoutAll } = useAuth();
  const { notify } = useToast();
  const [error, setError] = useState<unknown>();
  const change = useMutation({
    mutationFn: (values: Record<string, unknown>) => authApi.changePassword(String(values.current_password), String(values.new_password)),
    onSuccess: (result) => notify(result.message),
  });
  return <><PageHeader eyebrow="Account" title="Security" description="Change your password or revoke every refresh session." /><Card><SmartForm fields={[{ name: "current_password", label: "Current password", type: "password", required: true }, { name: "new_password", label: "New password", type: "password", required: true }]} submitLabel="Change password" busy={change.isPending} error={change.error} onSubmit={(values) => change.mutate(values)} /><hr /><button className="danger" onClick={() => void logoutAll().catch(setError)}>Sign out all sessions</button>{Boolean(error) && <div className="inline-error">Unable to revoke sessions.</div>}</Card></>;
}
