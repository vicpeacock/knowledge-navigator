/**Authentication and User types*/

export interface User {
  id: string;
  email: string;
  name: string | null;
  role: 'admin' | 'user' | 'viewer';
  tenant_id: string;
  email_verified: boolean;
  active?: boolean;
  created_at?: string;
  last_login_at?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name?: string;
  tenant_id?: string;
}

export interface RegisterResponse {
  user_id: string;
  email: string;
  name: string | null;
  email_verification_required: boolean;
  verification_token?: string; // Only in dev
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  access_token: string;
  expires_in: number;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}

export interface UserCreate {
  email: string;
  name?: string;
  password?: string;
  role?: 'admin' | 'user' | 'viewer';
  send_invitation_email?: boolean;
}

export interface UserUpdate {
  name?: string;
  role?: 'admin' | 'user' | 'viewer';
  active?: boolean;
}

export interface UserResponse {
  id: string;
  email: string;
  name: string | null;
  role: string;
  active: boolean;
  email_verified: boolean;
  last_login_at: string | null;
  created_at: string;
}

