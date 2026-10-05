export type User = { id: string; name: string; username: string; role: string };
export type Channel = {
  id: number;
  name: string;
  handle: string;
  niche: string;
  lang: string;
  autonomy: string;
  cadence_days: string;
  cadence_anchor: string;
  responsible_id: string | null;
  post_time: string;
  connected: number;
  key: string;
  template_key: string;
  format: string;
  accent: string;
  initials: string;
  target_stock: number;
  freshness_hours: number;
  enabled: number;
  paused: number;
  budget: number;
  instructions: string;
  revision: number;
  ready: number;
  total: number;
  producing: number;
  awaiting_review: number;
  scheduled: number;
  next_post: string;
  days_ahead: number;
  delivered: number;
  published: number;
};
export type Source = {
  id: string;
  name: string;
  url: string;
  published?: string;
};
export type Video = {
  id: string;
  channel_id: number;
  title: string;
  status: string;
  minutes: number;
  script: string;
  description: string;
  tags: string[];
  sources: Source[];
  notes: string;
  post_at: string;
  event_at: string;
  engine_ref: Record<string, unknown>;
  thumb_path: string;
  video_path: string;
  external_url: string;
  youtube_id: string;
  quality_status: string;
  rights_status: string;
  render_digest: string;
  approved_digest: string;
  cost: number | null;
  cost_cap: number;
  error: string;
  revision: number;
  created_at: string;
  updated_at: string;
};
export type Task = {
  id: string;
  title: string;
  channel_id: number | null;
  video_id: string | null;
  assignee: string;
  priority: string;
  due_at: string;
  done: number;
  revision: number;
};
export type Job = {
  id: string;
  kind: string;
  video_id: string | null;
  status: string;
  progress: number;
  message: string;
  error: string;
};
export type Activity = {
  id: number;
  actor: string;
  action: string;
  message: string;
  created_at: string;
};
export type Alert = {
  kind: string;
  channel_id?: number;
  video_id?: string;
  title: string;
  message: string;
};
export type Workspace = {
  channels: Channel[];
  videos: Video[];
  tasks: Task[];
  jobs: Job[];
  users: User[];
  activity: Activity[];
  alerts: Alert[];
  today: Video[];
  stats: {
    channels: number;
    ready: number;
    producing: number;
    review: number;
    scheduled: number;
  };
  settings: {
    paused: number;
    daily_budget: number;
    timezone: string;
    revision: number;
  };
  connections: Record<string, boolean>;
  worker: { heartbeat: string; message: string };
  server_time: string;
  control: { total: number; unread: number; critical: number };
};
export type Page =
  | "overview"
  | "channels"
  | "production"
  | "calendar"
  | "tasks"
  | "studio"
  | "library"
  | "settings"
  | "news"
  | "control"
  | "agent";
export type Boot = {
  user: User | null;
  csrf: string;
  setup_required: boolean;
  preview: boolean;
};
export type Message = {
  id: number;
  role: string;
  content: string;
  actor: string;
  created_at: string;
};
