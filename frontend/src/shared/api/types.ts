export type Status = "PENDING" | "IN_PROGRESS" | "RESOLVED" | "REJECTED";
export type Priority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";
export interface Directorate {
  id: number;
  name: string;
  description: string;
  location: string;
  is_active: boolean;
  current_manager?: { employee_id: number; full_name: string } | null;
}
export interface Citizen {
  id: number;
  first_name: string;
  last_name: string;
  phone: string;
  national_id: string;
  telegram_id?: number | null;
}
export interface PermissionScope {
  scope_type: "global" | "directorate";
  directorate_ids: number[] | null;
}
export interface Assignment {
  id: number;
  employee_id: number;
  role_id: number;
  scope_type: "global" | "directorate";
  directorate_id: number | null;
}
export interface SessionEmployee {
  id: number;
  user_id: number;
  username: string;
  full_name: string;
  role: string;
  directorate_id: number | null;
  is_demo: boolean;
  password_version: number;
  roles: {
    id: number;
    code: string;
    name: string;
    scope_type: string;
    directorate_id: number | null;
  }[];
  permissions: Record<string, PermissionScope>;
}
export interface Employee {
  id: number;
  user_id: number;
  username: string;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  email: string | null;
  is_active: boolean;
  needs_profile_completion: boolean;
  directorate_id: number | null;
  role_assignments: Assignment[];
}
export interface Role {
  id: number;
  code: string;
  name: string;
  description: string;
  is_system: boolean;
  permissions: string[];
}
export interface Permission {
  code: string;
  name: string;
  description: string;
}
export interface Language {
  code: string;
  name: string;
  direction: "rtl" | "ltr";
  is_active?: boolean;
}
export interface Translation {
  language_code: string;
  name: string;
  description: string;
  location?: string;
}
export interface Page<T> {
  total: number;
  page: number;
  items: T[];
}
export interface Notification {
  status: string;
  message: string;
}
export interface Note {
  id: number;
  note: string;
  is_internal: boolean;
  audience: "internal" | "private" | "public";
  created_at: string;
  author_name?: string;
  notification_status?: string;
  notification_error?: string | null;
}
export interface FileAttachment {
  id: number;
  file_id?: number;
  file_type: string;
  name?: string;
  file_url: string;
}
export interface EvidenceReply {
  id: number;
  text: string;
  channel: string;
  created_at: string;
  attachments: FileAttachment[];
}
export interface EvidenceRequest {
  id: number;
  complaint_id: number;
  prompt: string;
  author_name: string;
  created_at: string;
  status: string;
  replies: EvidenceReply[];
  notification_status?: string;
  notification_error?: string | null;
}
export interface PublicReview {
  hidden: boolean;
  message: string;
  history: {
    id: number;
    action: string;
    reason: string;
    message: string;
    created_at: string;
    author_name?: string;
    notification_status?: string;
  }[];
  reports?: { id: number; reason: string; created_at: string; review_id: number | null }[];
}
export interface Complaint {
  id: number;
  tracking_code: string;
  directorate_id: number;
  title: string;
  details: string;
  category: string;
  is_public: boolean;
  public_review: PublicReview;
  priority: Priority;
  status: Status;
  created_at: string;
  updated_at: string | null;
  progress: number;
  resolution_report: string;
  notes: Note[];
  admin_notes: string;
  attachments: FileAttachment[];
  evidence_requests: EvidenceRequest[];
  citizen?: Omit<Citizen, "id">;
}
export interface ComplaintInput {
  citizen_id: number;
  directorate_id: number;
  title: string;
  details: string;
  category: string;
  priority?: Priority;
  is_public: boolean;
  latitude?: number;
  longitude?: number;
}
export interface ProcessingInput {
  progress?: number;
  resolution_report?: string;
  priority?: Priority;
  admin_notes?: string;
  reason?: string;
}
export interface HistoryEvent {
  id: number;
  event: string;
  old_status: string | null;
  new_status: string;
  old_directorate_id: number | null;
  new_directorate_id: number;
  old_progress: number | null;
  new_progress: number;
  created_at: string;
  reason?: string;
  actor_user_id?: number;
  source?: string;
}
export interface AuditEvent {
  id: number;
  actor_user_id: number | null;
  action: string;
  entity_type: string;
  entity_id: string;
  changes: Record<string, unknown>;
  source: string;
  request_id: string;
  created_at: string;
}
