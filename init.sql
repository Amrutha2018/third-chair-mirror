
-- Set up the necessary extension
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

-- Enum types
CREATE TYPE public.crawl_status_enum_v1 AS ENUM ('MATCHED', 'NO_MATCH', 'ERROR');
CREATE TYPE public.job_event_type_v1 AS ENUM ('CRAWL_READY', 'OUTREACH_READY', 'LETTER_GENERATION_READY', 'SENT_MAIL_READY', 'SENT_MAIL');
CREATE TYPE public.outreach_status_v1 AS ENUM (
    'NOT_CONTACTED', 'SENT_1ST_MAIL', 'SENT_2ND_MAIL', 'SENT_3RD_MAIL', 'SENT_4TH_MAIL',
    'REPLIED', 'BOUNCED', 'FAILED', 'REPLIED_BY_US', 'NUDGED_AGAIN',
    'LEGAL_LETTER_READY', 'LEGAL_LETTER_SENT', 'COURT_READY', 'COURT_NOTICE_SENT'
);
CREATE TYPE public.status_enum_v1 AS ENUM ('PENDING', 'CRAWLING', 'OUTREACHING', 'GENERATING_LETTER', 'COMPLETED', 'FAILED');
CREATE TYPE public.status_enum_v2 AS ENUM ('PENDING', 'CRAWLING', 'OUTREACHING', 'GENERATING_LETTER', 'SENT_MAIL', 'COMPLETED', 'FAILED', 'COURT_NOTICE_SENT');

-- Sequence
CREATE SEQUENCE public.job_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Tables
CREATE TABLE public.jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    input_text text,
    filters jsonb,
    status public.status_enum_v2 DEFAULT 'PENDING' NOT NULL,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (id)
);

CREATE TABLE public.crawl_events (
    id integer NOT NULL DEFAULT nextval('public.job_events_id_seq'),
    job_id uuid,
    created_at timestamp DEFAULT now(),
    is_processing boolean DEFAULT false,
    progress_updated_at timestamp,
    PRIMARY KEY (id),
    FOREIGN KEY (job_id) REFERENCES public.jobs(id) ON DELETE CASCADE
);

CREATE TABLE public.crawl_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    job_id uuid,
    url text NOT NULL,
    matched_snippet text,
    match_score integer,
    screenshot_path text,
    ots_path text,
    "timestamp" timestamptz DEFAULT now(),
    status public.crawl_status_enum_v1 NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (job_id) REFERENCES public.jobs(id) ON DELETE CASCADE
);

CREATE TABLE public.outreach_contacts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    job_id uuid,
    crawl_result_id uuid,
    email text,
    status public.outreach_status_v1 DEFAULT 'NOT_CONTACTED',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    source text CHECK (source = ANY (ARRAY['html', 'mailto', 'guessed', 'whois'])),
    is_processing boolean DEFAULT false,
    last_reply_text text,
    reply_received_at timestamptz DEFAULT now(),
    PRIMARY KEY (id),
    FOREIGN KEY (job_id) REFERENCES public.jobs(id),
    FOREIGN KEY (crawl_result_id) REFERENCES public.crawl_results(id)
);

CREATE TABLE public.replies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    contact_id uuid,
    original_reply text,
    llm_draft text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    status text DEFAULT 'DRAFTED',
    PRIMARY KEY (id),
    FOREIGN KEY (contact_id) REFERENCES public.outreach_contacts(id)
);

CREATE TABLE public.test_email_map (
    job_id uuid NOT NULL,
    test_email text NOT NULL,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (job_id),
    FOREIGN KEY (job_id) REFERENCES public.jobs(id)
);
