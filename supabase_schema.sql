-- ============================================================
-- UniSync — Supabase Database Schema
-- Run this in: Supabase Dashboard > SQL Editor
-- ============================================================

-- ============================================================
-- 1. PROFILES TABLE (linked to auth.users)
-- ============================================================
create table if not exists public.profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    email       text,
    full_name   text,
    student_id  text,
    role        text default 'student' check (role in ('admin','teacher','student')),
    dept        text default 'Management',
    batch       text,
    created_at  timestamptz default now()
);

-- RLS
alter table public.profiles enable row level security;

create policy "Users can read own profile"
    on public.profiles for select
    using (auth.uid() = id);

create policy "Users can update own profile"
    on public.profiles for update
    using (auth.uid() = id);

create policy "Admins can read all profiles"
    on public.profiles for select
    using (
        exists (
            select 1 from public.profiles p
            where p.id = auth.uid() and p.role = 'admin'
        )
    );

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
    insert into public.profiles (id, email, full_name)
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data->>'full_name', '')
    )
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();


-- ============================================================
-- 2. MAPPINGS TABLE (course & teacher code -> full name)
-- ============================================================
create table if not exists public.mappings (
    code        text primary key,
    full_name   text not null,
    type        text default 'course' check (type in ('course','teacher')),
    created_at  timestamptz default now()
);

alter table public.mappings enable row level security;

create policy "Anyone can read mappings"
    on public.mappings for select
    using (true);

create policy "Service role can manage mappings"
    on public.mappings for all
    using (true);


-- ============================================================
-- 3. ROUTINES TABLE
-- ============================================================
create table if not exists public.routines (
    id           uuid primary key default gen_random_uuid(),
    day          text not null check (day in ('Sunday','Monday','Tuesday','Wednesday','Thursday')),
    room_no      text not null,
    time_slot    text not null,
    time_start   text not null,
    time_end     text not null,
    course_code  text references public.mappings(code) on delete set null,
    teacher_code text references public.mappings(code) on delete set null,
    session      text default '2025-26',
    created_at   timestamptz default now()
);

alter table public.routines enable row level security;

create policy "Anyone can read routines"
    on public.routines for select
    using (true);

create policy "Service role can manage routines"
    on public.routines for all
    using (true);

create index if not exists idx_routines_day on public.routines(day);
create index if not exists idx_routines_time on public.routines(time_start, time_end);


-- ============================================================
-- 4. TASKS TABLE
-- ============================================================
create table if not exists public.tasks (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid references public.profiles(id) on delete cascade,
    title        text not null,
    description  text,
    deadline     timestamptz,
    priority     text default 'medium' check (priority in ('low','medium','high')),
    status       text default 'pending' check (status in ('pending','in_progress','done')),
    course_code  text,
    created_at   timestamptz default now(),
    updated_at   timestamptz default now()
);

alter table public.tasks enable row level security;

create policy "Users can manage own tasks"
    on public.tasks for all
    using (auth.uid() = user_id);

create index if not exists idx_tasks_user_id on public.tasks(user_id);
create index if not exists idx_tasks_deadline on public.tasks(deadline);


-- ============================================================
-- 5. RESOURCES TABLE
-- ============================================================
create table if not exists public.resources (
    id           uuid primary key default gen_random_uuid(),
    dept         text default 'Management',
    subject      text,
    title        text,
    file_url     text,
    uploaded_by  text,
    created_at   timestamptz default now()
);

alter table public.resources enable row level security;

create policy "Anyone can read resources"
    on public.resources for select
    using (true);

create policy "Authenticated users can insert resources"
    on public.resources for insert
    with check (auth.role() = 'authenticated');

create index if not exists idx_resources_dept on public.resources(dept);


-- ============================================================
-- DONE! Now go to the UniSync Admin Panel and click
-- "Seed Routine & Mappings" to populate the schedule.
-- ============================================================
