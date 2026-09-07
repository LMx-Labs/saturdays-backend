import { api } from "../client";
import type { AuthTokens, MessageResponse, User } from "../types";

export const authApi = {
  me: () => api.get<User>("/auth/me"),
  forgotPassword: (email: string) => api.post<MessageResponse>("/auth/password/forgot", { email }),
  resetPassword: (token: string, newPassword: string) =>
    api.post<MessageResponse>("/auth/password/reset", { token, new_password: newPassword }),
  changePassword: (currentPassword: string, newPassword: string) =>
    api.post<MessageResponse>("/auth/password/change", {
      current_password: currentPassword,
      new_password: newPassword,
    }),
  verifyEmail: (token: string) => api.post<MessageResponse>("/auth/verify-email", { token }),
  resendVerification: (email: string) =>
    api.post<MessageResponse>("/auth/verification/resend", { email }),
  acceptInvitation: (token: string, password: string) =>
    api.post<AuthTokens>("/auth/invitations/accept", { token, password }),
};
