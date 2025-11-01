--
-- PostgreSQL database dump
--

\restrict fvahrPMApMRkebMy3fuoxB7yx3ymFB64OvsMFwnT3ZA66RgbBXBuLVKmZzRgt9p

-- Dumped from database version 15.14
-- Dumped by pg_dump version 15.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: emailurgency; Type: TYPE; Schema: public; Owner: disruptiq
--

CREATE TYPE public.emailurgency AS ENUM (
    'URGENT',
    'IMPORTANT',
    'ROUTINE'
);


ALTER TYPE public.emailurgency OWNER TO disruptiq;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: coproprietaires; Type: TABLE; Schema: public; Owner: disruptiq
--

CREATE TABLE public.coproprietaires (
    id integer NOT NULL,
    nom character varying NOT NULL,
    prenom character varying NOT NULL,
    email character varying,
    telephone character varying,
    telephone_mobile character varying,
    copropriete_id integer NOT NULL,
    numero_lot character varying NOT NULL,
    type_lot character varying,
    etage integer,
    surface numeric(8,2),
    statut character varying DEFAULT 'proprietaire'::character varying,
    statut_special character varying,
    est_resident boolean DEFAULT true,
    date_acquisition date,
    tantiemes integer,
    adresse_postale text,
    preferences_contact jsonb DEFAULT '{"sms": false, "email": true}'::jsonb,
    notes text,
    is_indexed boolean DEFAULT false NOT NULL,
    last_indexed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.coproprietaires OWNER TO disruptiq;

--
-- Name: coproprietaires_id_seq; Type: SEQUENCE; Schema: public; Owner: disruptiq
--

CREATE SEQUENCE public.coproprietaires_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.coproprietaires_id_seq OWNER TO disruptiq;

--
-- Name: coproprietaires_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: disruptiq
--

ALTER SEQUENCE public.coproprietaires_id_seq OWNED BY public.coproprietaires.id;


--
-- Name: coproprietes; Type: TABLE; Schema: public; Owner: disruptiq
--

CREATE TABLE public.coproprietes (
    id integer NOT NULL,
    nom character varying NOT NULL,
    adresse text NOT NULL,
    ville character varying NOT NULL,
    code_postal character varying(10) NOT NULL,
    nombre_lots integer,
    nombre_batiments integer DEFAULT 1,
    annee_construction integer,
    syndic character varying,
    contact_syndic character varying,
    reference_syndic character varying,
    type_copropriete character varying,
    surface_totale numeric(10,2),
    equipements jsonb DEFAULT '[]'::jsonb,
    notes text,
    documents_path character varying,
    is_indexed boolean DEFAULT false NOT NULL,
    last_indexed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.coproprietes OWNER TO disruptiq;

--
-- Name: coproprietes_id_seq; Type: SEQUENCE; Schema: public; Owner: disruptiq
--

CREATE SEQUENCE public.coproprietes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.coproprietes_id_seq OWNER TO disruptiq;

--
-- Name: coproprietes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: disruptiq
--

ALTER SEQUENCE public.coproprietes_id_seq OWNED BY public.coproprietes.id;


--
-- Name: documents; Type: TABLE; Schema: public; Owner: disruptiq
--

CREATE TABLE public.documents (
    id integer NOT NULL,
    filename character varying NOT NULL,
    original_filename character varying NOT NULL,
    file_path character varying,
    file_size bigint,
    mime_type character varying,
    document_type character varying,
    category character varying,
    tags json,
    extracted_text text,
    summary text,
    qdrant_id character varying,
    vendor_id integer,
    property_id character varying,
    document_metadata json,
    processed boolean,
    indexed boolean,
    document_date timestamp with time zone,
    uploaded_at timestamp with time zone DEFAULT now(),
    processed_at timestamp with time zone,
    professionnel_id integer,
    copropriete_id integer,
    coproprietaire_id integer
);


ALTER TABLE public.documents OWNER TO disruptiq;

--
-- Name: documents_id_seq; Type: SEQUENCE; Schema: public; Owner: disruptiq
--

CREATE SEQUENCE public.documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.documents_id_seq OWNER TO disruptiq;

--
-- Name: documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: disruptiq
--

ALTER SEQUENCE public.documents_id_seq OWNED BY public.documents.id;


--
-- Name: emails; Type: TABLE; Schema: public; Owner: disruptiq
--

CREATE TABLE public.emails (
    id integer NOT NULL,
    message_id character varying,
    thread_id character varying,
    sender character varying NOT NULL,
    recipient character varying,
    subject character varying NOT NULL,
    body text,
    urgency public.emailurgency,
    category character varying,
    attachments json,
    llm_analysis json,
    processed boolean,
    included_in_digest boolean,
    received_at timestamp with time zone,
    processed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    professionnel_id integer,
    copropriete_id integer,
    coproprietaire_id integer
);


ALTER TABLE public.emails OWNER TO disruptiq;

--
-- Name: emails_id_seq; Type: SEQUENCE; Schema: public; Owner: disruptiq
--

CREATE SEQUENCE public.emails_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.emails_id_seq OWNER TO disruptiq;

--
-- Name: emails_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: disruptiq
--

ALTER SEQUENCE public.emails_id_seq OWNED BY public.emails.id;


--
-- Name: professionnels; Type: TABLE; Schema: public; Owner: disruptiq
--

CREATE TABLE public.professionnels (
    id integer NOT NULL,
    name character varying NOT NULL,
    company_name character varying,
    email character varying NOT NULL,
    phone character varying,
    category character varying,
    specialties json,
    address text,
    city character varying,
    postal_code character varying,
    rating double precision,
    total_jobs integer,
    last_contacted timestamp with time zone,
    notes text,
    is_indexed boolean NOT NULL,
    last_indexed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    siret character varying(14),
    description text,
    statut character varying(20) DEFAULT 'active'::character varying
);


ALTER TABLE public.professionnels OWNER TO disruptiq;

--
-- Name: professionnels_coproprietes; Type: TABLE; Schema: public; Owner: disruptiq
--

CREATE TABLE public.professionnels_coproprietes (
    professionnel_id integer NOT NULL,
    copropriete_id integer NOT NULL,
    date_debut date DEFAULT CURRENT_DATE,
    date_fin date,
    est_prestataire_principal boolean DEFAULT false,
    nombre_interventions integer DEFAULT 0,
    derniere_intervention timestamp with time zone,
    note_moyenne numeric(3,2),
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.professionnels_coproprietes OWNER TO disruptiq;

--
-- Name: professionnels_id_seq; Type: SEQUENCE; Schema: public; Owner: disruptiq
--

CREATE SEQUENCE public.professionnels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.professionnels_id_seq OWNER TO disruptiq;

--
-- Name: professionnels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: disruptiq
--

ALTER SEQUENCE public.professionnels_id_seq OWNED BY public.professionnels.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: disruptiq
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying NOT NULL,
    hashed_password character varying NOT NULL,
    full_name character varying,
    is_active boolean,
    is_superuser boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.users OWNER TO disruptiq;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: disruptiq
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO disruptiq;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: disruptiq
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: coproprietaires id; Type: DEFAULT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.coproprietaires ALTER COLUMN id SET DEFAULT nextval('public.coproprietaires_id_seq'::regclass);


--
-- Name: coproprietes id; Type: DEFAULT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.coproprietes ALTER COLUMN id SET DEFAULT nextval('public.coproprietes_id_seq'::regclass);


--
-- Name: documents id; Type: DEFAULT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);


--
-- Name: emails id; Type: DEFAULT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.emails ALTER COLUMN id SET DEFAULT nextval('public.emails_id_seq'::regclass);


--
-- Name: professionnels id; Type: DEFAULT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.professionnels ALTER COLUMN id SET DEFAULT nextval('public.professionnels_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: coproprietaires; Type: TABLE DATA; Schema: public; Owner: disruptiq
--

COPY public.coproprietaires (id, nom, prenom, email, telephone, telephone_mobile, copropriete_id, numero_lot, type_lot, etage, surface, statut, statut_special, est_resident, date_acquisition, tantiemes, adresse_postale, preferences_contact, notes, is_indexed, last_indexed_at, created_at, updated_at) FROM stdin;
1	Dupont	Marie	marie.dupont@example.fr	0145678901	0612345678	1	A12	appartement	3	65.50	proprietaire	président	t	\N	850	\N	{"sms": false, "email": true}	\N	f	\N	2025-11-01 13:49:12.846194+00	\N
\.


--
-- Data for Name: coproprietes; Type: TABLE DATA; Schema: public; Owner: disruptiq
--

COPY public.coproprietes (id, nom, adresse, ville, code_postal, nombre_lots, nombre_batiments, annee_construction, syndic, contact_syndic, reference_syndic, type_copropriete, surface_totale, equipements, notes, documents_path, is_indexed, last_indexed_at, created_at, updated_at) FROM stdin;
1	Résidence Les Mimosas	12 Avenue de la République	Paris	75013	45	2	1985		\N	\N	résidentiel	\N	["ascenseur", "parking", "interphone"]	\N	\N	f	\N	2025-11-01 13:49:00.023333+00	2025-11-01 16:26:04.988756+00
\.


--
-- Data for Name: documents; Type: TABLE DATA; Schema: public; Owner: disruptiq
--

COPY public.documents (id, filename, original_filename, file_path, file_size, mime_type, document_type, category, tags, extracted_text, summary, qdrant_id, vendor_id, property_id, document_metadata, processed, indexed, document_date, uploaded_at, processed_at, professionnel_id, copropriete_id, coproprietaire_id) FROM stdin;
\.


--
-- Data for Name: emails; Type: TABLE DATA; Schema: public; Owner: disruptiq
--

COPY public.emails (id, message_id, thread_id, sender, recipient, subject, body, urgency, category, attachments, llm_analysis, processed, included_in_digest, received_at, processed_at, created_at, professionnel_id, copropriete_id, coproprietaire_id) FROM stdin;
1	19a3e73e1bad4c01	19a3e73e1bad4c01	"Booking.com" <email.campaign@sg.booking.com>	\N	Gregori, il ne vous reste plus que 6 jours pour récupérer jusqu'à € 100 de crédit ! ⏳	<!doctype html>\r\n      <html\r\n        lang="fr"\r\n        dir=ltr\r\n        xmlns="http://www.w3.org/1999/xhtml"\r\n        xmlns:v="urn:schemas-microsoft-com:vml"\r\n        xmlns:o="urn:schemas-microsoft-com:office:office"\r\n      >\r\n        <head>\r\n          <meta http-equiv="content-type" content="text/html; charset=UTF-8" />\r\n          <meta http-equiv="content-style-type" content="text/css" />\r\n          <meta name="robots" content="index,follow" />\r\n          <meta\r\n            name="viewport"\r\n            content="width=device-width, initial-scale=1.0"\r\n          />\r\n          <style type="text/css">\r\n      body {\r\n        -webkit-text-size-adjust: 100%;\r\n        -ms-text-size-adjust: 100%;\r\n      }\r\n      body {\r\n        -webkit-font-smoothing: antialiased;\r\n      }\r\n      body {\r\n        margin: 0 auto !important;\r\n        padding: 0;\r\n      }\r\n      body {\r\n        width: 100% !important;\r\n      }\r\n      table {\r\n        border-spacing: 0;\r\n      }\r\n      img {\r\n        border: 0 none;\r\n        line-height: 100%;\r\n        outline: none;\r\n        text-decoration: none;\r\n        -ms-interpolation-mode: bicubic;\r\n      }\r\n      a img {\r\n        border: 0 none;\r\n        text-decoration: none;\r\n      }\r\n      table td {\r\n        border-collapse: collapse;\r\n      }\r\n      table {\r\n        border-collapse: collapse;\r\n        mso-table-lspace: 0pt;\r\n        mso-table-rspace: 0pt;\r\n      }\r\n      body {\r\n        -webkit-font-smoothing: auto;\r\n      }\r\n      strong {\r\n        font-weight: bold;\r\n      }\r\n      .appleLinksBlack {\r\n        color: #000000 !important;\r\n        text-decoration: none !important;\r\n      }\r\n      a[x-apple-data-detectors] {\r\n        color: inherit !important;\r\n        text-decoration: none !important;\r\n        font-size: inherit !important;\r\n        font-family: inherit !important;\r\n        font-weight: inherit !important;\r\n        line-height: inherit !important;\r\n      }\r\n      @media only screen and (max-width: 575px) {\r\n        .m-hide {\r\n          display: none !important;\r\n        }\r\n        .m-block {\r\n          display: block !important;\r\n        }\r\n        .m-tr {\r\n          display: table-row !important;\r\n        }\r\n        .m-w-full {\r\n          width: 100% !important;\r\n        }\r\n        .m-w-auto {\r\n          width: auto !important;\r\n        }\r\n        .m-m-auto {\r\n          margin: 0 auto !important;\r\n        }\r\n        .m-text-center {\r\n          text-align: center !important;\r\n        }\r\n        .m-text-right {\r\n          text-align: right !important;\r\n        }\r\n        .m-text-left {\r\n          text-align: left !important;\r\n        }\r\n      }\r\n  </style>\r\n  <style data-react-helmet="true" >.links-black, .links-black div, .links-black a, a[x-apple-data-detectors] {\r\n    color: #1a1a1a !important;\r\n    text-decoration: none !important;\r\n  }</style><style data-react-helmet="true" >body { margin: 0px;padding: 0px; }</style><style data-react-helmet="true" >@media only screen and (max-width: 575px) {.bui-mobile-1-R15n5gr{text-align: center !important;}}</style><style data-react-helmet="true" >@media only screen and (max-width: 575px) {.bui-mobile-4-R7eppn5gr.bui-mobile-4-R7eppn5gr{display: table-cell !important;}}</style><style data-react-helmet="true" >@media only screen and (max-width: 575px) {.bui-mobile-5-R9eppn5gr.bui-mobile-5-R9eppn5gr{display: table-cell !important;}}</style><style data-react-helmet="true" >@media only screen and (max-width: 575px) {.bui-mobile-3-Reppn5gr{text-align: right !important;}}</style><style data-react-helmet="true" >@media only screen and (max-width: 575px) {.bui-mobile-6-Rbeppn5gr.bui-mobile-6-Rbeppn5gr{display: table-cell !important;}}</style><style data-react-helmet="true" >@media only screen and (max-width: 575px) {.bui-mobile-2-R9n5gr.bui-mobile-2-R9n5gr{display: none !important;}}</style><style data-react-helmet="true" >@media only screen and (max-width: 575px) {.bui-mobile-7-R3b5r{width: 100% !important;}}</style>\r\n          <title>Gregori, il ne vous reste plus que 6 jours pour récupérer jusqu'à € 100 de crédit ! ⏳</title>\r\n        </head>\r\n        <body style="background-color: #ffffff; margin: 0;" id="content-viewport">\r\n          <div><!--[if mso | IE]>\r\n<style>body, table, td, th { font-family: BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif !important; }</style>\r\n<![endif]--></div><div style="font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><div style="display:none;overflow:hidden;line-height:1px;opacity:0;max-height:0;max-width:0">Dernière chance d&#x27;utiliser votre code promo de 10 %<div> ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿ ‌​‍‎‏﻿</div></div><table align="center" border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr dir="ltr"><td><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td style="background-color:#003b95;color:#ffffff;padding-left:16px;padding-right:16px"><div><!--[if mso | IE]>\r\n<table align="center" border="0" cellspacing="0" cellpadding="0" width="624" role="presentation">\r\n<tbody><tr><td valign="top" width="624">\r\n<![endif]--></div><table align="center" border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%" style="max-width:624px"><tbody><tr><td><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td style="padding-top:16px;padding-bottom:16px"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" style="width:100%;display:table"><tbody style="width:100%;display:table-row-group"><tr style="width:100%;display:table-row"><td class="bui-mobile-1-R15n5gr" style="width:50%;display:table-cell;text-align:left;vertical-align:middle;font-weight:normal"><a universal="true" data-msys-sublink="uni" href="https://link.sg.booking.com/uni/ss/c/u001.8r4wBKx-pJaaWDSVmzpav7OGgBFXOu2xc8Dirf24IGJyPDMWZfoBvyneWVEN1vzEdAt2izZkEyaHqJv3vYoFORdwRJIEThU_l5Yh6BdijKzcFd_maJW932EYuPLf7A_88hKncnZUeFCEQ1V6NrKAG8KYS5Vvet82AMxXj55RtHvzn8TBEfOhXA9c9gUfD-Hk/4l8/DYzXM6UhTMSjsFlzBG0kgA/h0/h001.sBOxi-TbNznMD66388w5v2Zo6fCuUfI-Aq-5mL8mrPw" style="text-decoration:none;color:inherit;display:inline-block;vertical-align:middle" target="_blank" rel="noreferrer"><img border="none" style="display:block;border:none;width:144px;height:24px" class="" height="24" width="144" src="https://r-xx.bstatic.com/data/mm/email_logo_white_trans_bg_01.png" alt="Booking.com"/></a></td><td class="bui-mobile-2-R9n5gr" style="width:100%;display:table-cell;text-align:right;vertical-align:middle;font-weight:normal"><table align="right" border="0" cellSpacing="0" cellPadding="0" role="presentation"><tbody><tr><td class="bui-mobile-4-R7eppn5gr" valign="middle" style="display:table-cell" width="34"><a universal="true" data-msys-sublink="uni" href="https://link.sg.booking.com/uni/ss/c/u001.r02JNj94M2Mnc8SJMDcfC3fzYWmBCLGNKOqH5o787mZpkL1oGn0n_Qsk0fMZfP1h5W5YWf8lx914TbsWkzFmA8nHTw-WWxMJKGzNUcj_5bWfFPMflRaMHIPp9PclscDdtNo2hj3yLicu_yPyOyyCNSSdrNZPoh0G2Xbg7m2UMT6ZSB_3ARkDz-RrOdm5mZdY5Pwqa79z488V7c5QgVRJKRxiua41-Y9yUTBMzLDtwew/4l8/DYzXM6UhTMSjsFlzBG0kgA/h1/h001.AJktWVpBvGMbSkYqBt4FK2S0l1hzjMgfuQXCxpwec9U" style="text-decoration:none;color:inherit;display:block" target="_blank" rel="noreferrer"><span style="border-radius:999px;display:block;width:30px;border:2px solid #ffb700"><img style="display:block;border:none;border-radius:999px;width:30px;height:30px" class="" height="30" width="30" src="https://lh3.googleusercontent.com/-bSaEfj3M9Xw/AAAAAAAAAAI/AAAAAAAAAAA/ACHi3rfqtqKB7pTvN3ntyMpPA3phAgpmBA/photo.jpg64" alt="💢"/></span></a></td><td class="bui-mobile-5-R9eppn5gr" style="width:8px;display:table-cell"><span style="height:8px;width:8px;display:block;line-height:0"><img style="height:8px;width:8px;line-height:0" src="https://r-xx.bstatic.com/static/img/transparent.gif" height="8" width="8" alt=""/></span></td><td class="bui-mobile-6-Rbeppn5gr bui-mobile-3-Reppn5gr" valign="middle" style="display:table-cell;text-align:left"><a universal="true" data-msys-sublink="uni" href="https://link.sg.booking.com/uni/ss/c/u001.r02JNj94M2Mnc8SJMDcfC3fzYWmBCLGNKOqH5o787mZpkL1oGn0n_Qsk0fMZfP1h5W5YWf8lx914TbsWkzFmA8nHTw-WWxMJKGzNUcj_5bWfFPMflRaMHIPp9PclscDdtNo2hj3yLicu_yPyOyyCNSSdrNZPoh0G2Xbg7m2UMT6ZSB_3ARkDz-RrOdm5mZdYPsWCcgXv0VBjWMK88iT3aL0tT36b01IN2wx_vZOMBIc/4l8/DYzXM6UhTMSjsFlzBG0kgA/h2/h001.0SHSdY3aRxA_1FPHtu2-Lx-y3Sq0S8JS0NX_KtTkasI" style="text-decoration:none;color:#ffffff" target="_blank" rel="noreferrer">Gregori Bonetto</a><table border="0" cellSpacing="0" cellPadding="0" role="presentation"><tbody><tr><td valign="middle"><div style="margin:0;color:#febb02"><span style="white-space:nowrap">Niveau 3 Genius</span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr></tbody></table></td></tr></tbody></table></td></tr></tbody></table><div><!--[if mso | IE]>\r\n</td></tr></tbody></table>\r\n<![endif]--></div></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="background-color:#ffffff;width:324px" valign="middle"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td height="24"></td></tr><tr><td class="" style="padding-right:24px;text-align:left;line-height:1px" align="left"><a href="https://link.sg.booking.com/uni/ss/c/u001.8r4wBKx-pJaaWDSVmzpav-WkRtZnxAg7dyKpOmVNDbaul04J0jot0svViWagzCy5XVJSw6aFHDkJmoMjfMniorg-RpXG_dfBGLZYGXFVlcs0oDwQXdwZa7fO8v4geaG4l3YfalX0FcYnWaFI9UCQRBZlaIzPaNV4p7ytxGxDGuSmPUDadVV-2GvHUL1LF9DrdcxLND2DuvBuNuLgObAaSA/4l8/DYzXM6UhTMSjsFlzBG0kgA/h3/h001.sBRYO91gaFM24-w7hlHBCk8R1kX1Cx0gQHTGngfCo38" target="_blank" rel="noreferrer" data-msys-sublink="uni" universal="true"><img width="64" height="64" style="display:block;max-width:100%;width:64px;height:64px" src="https://q-xx.bstatic.com/data/mm/bell_Icon_rem_postTrip_incen.png" alt="Bell"/></a></td></tr><tr><td class="" style="padding-right:24px;text-align:left;line-height:1px" align="left"><img src="https://r-xx.bstatic.com/static/img/transparent.gif" height="12" width="1" role="presentation" style="height:12px"/></td></tr><tr><td class="" style="padding-right:24px;text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:inherit;font-size:24px;line-height:32px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Dernière chance d'utiliser votre code promo de 10 %</span></span></div></td></tr><tr><td class="" style="padding-right:24px;text-align:left;line-height:1px" align="left"><img src="https://r-xx.bstatic.com/static/img/transparent.gif" height="12" width="1" role="presentation" style="height:12px"/></td></tr><tr><td class="" style="padding-right:24px;text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:inherit;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span><span style="color: #6b6b6b">Expire le 7 novembre 2025 (inclus)</span></span></span></div></td></tr><tr><td class="" style="padding-right:24px;text-align:left;line-height:1px" align="left"><img src="https://r-xx.bstatic.com/static/img/transparent.gif" height="16" width="1" role="presentation" style="height:16px"/></td></tr><tr><td height="24"></td></tr></tbody></table></td><td class="m-hide" style="width:300px" valign="middle"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><a href="https://link.sg.booking.com/uni/ss/c/u001.8r4wBKx-pJaaWDSVmzpav-WkRtZnxAg7dyKpOmVNDbaul04J0jot0svViWagzCy5_nMB2e9rIwiPfGTFloeT740TJeaO-KRjM9mojZ6tAIQNfk3QIokz3NsP_b13g5xWOdki9HLvx85zUCGGLlNhzth1CJZVpsLWE-nouKgyom7cETMTLTUoYRgznWS4rGRKjDDhsjvpYE8p6lUnXek5lA/4l8/DYzXM6UhTMSjsFlzBG0kgA/h4/h001.qC91qwFnWJvB5mBvzARGIpiXLqJBSOMf5W93nPz2vKo" target="_blank" rel="noreferrer" data-msys-sublink="uni" universal="true"><img width="324" style="display:block;max-width:100%;width:324px" src="https://r-xx.bstatic.com/data/mm/hero_post_trip_incen_rem.png" alt="Hero image"/></a></td></tr></tbody></table></td></tr></tbody></table></td></tr><!--[if !mso]><!--><tr class="m-tr" style="display:none"><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="width:624px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><a href="https://link.sg.booking.com/uni/ss/c/u001.8r4wBKx-pJaaWDSVmzpav-WkRtZnxAg7dyKpOmVNDbaul04J0jot0svViWagzCy5AMR5rqNXBzfWojwE1eGqLp-zEoNfD7VWG6x9_OCbyJwPy60veJB3avADY7Ypz2eaiSgFR7cRvxiq6yiWI1k5SYd1cy6pauM4e8YGBfsGWC3NnsOcM1HW7sywxntPaTme/4l8/DYzXM6UhTMSjsFlzBG0kgA/h5/h001.zXDNcHzNeKQQE_mQA1WrJvvRkG2z7nRFKSS_PTYVFwE" target="_blank" rel="noreferrer" data-msys-sublink="uni" universal="true"><img width="624" style="display:block;max-width:100%;width:624px" src="https://r-xx.bstatic.com/data/mm/hero_post_trip_incen_rem.png" alt="Hero image"/></a></td></tr></tbody></table></td></tr></tbody></table></td></tr><!--<![endif]--><tr class=""><td style="background-color:#ffffff;padding:16px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="width:624px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:inherit;font-size:16px;line-height:24px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Bonjour Gregori,</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:16px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="width:624px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:inherit;font-size:16px;line-height:24px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>C'est votre dernière chance pour profiter de votre récompense.</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:16px 16px 16px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="width:624px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:inherit;font-size:16px;line-height:24px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Votre code expire dans 6 jour. Réservez maintenant pour récupérer 10 % du montant de votre réservation sous forme de Crédit de Voyage (montant maximum de € 100) après votre séjour.</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:16px 16px 16px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="width:624px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:inherit;font-size:16px;line-height:24px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Vous préférez attendre un peu avant de voyager ? Réservez un séjour pour la date de votre choix. Nous proposons l'annulation gratuite dans la plupart des établissements.</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:24px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="background-color:#f5f5f5;width:624px;border-radius:8px 8px 0px 0px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td height="24"></td></tr><tr><td class="" style="padding-left:16px;padding-right:16px;text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:16px;line-height:24px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Votre code promo pour profiter d'un crédit de 10 %</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="background-color:#f5f5f5;width:624px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td height="8"></td></tr><tr><td class="" style="padding-left:16px;padding-right:16px;text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:inherit;font-size:20px;line-height:28px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>5Q9KSMZ5RX</span></span></div></td></tr><tr><td height="8"></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 24px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="background-color:#f5f5f5;width:624px;border-radius:0px 0px 8px 8px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="padding-left:16px;padding-right:16px;text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:16px;line-height:24px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Cliquez sur le bouton ci-dessous pour activer votre code, ou saisissez-le au moment de choisir votre moyen de paiement, juste avant de réserver.</span></span></div></td></tr><tr><td height="24"></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:24px 16px 24px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="width:624px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><a universal="true" data-msys-sublink="uni" class="bui-mobile-7-R3b5r" href="https://link.sg.booking.com/uni/ss/c/u001.8r4wBKx-pJaaWDSVmzpav-WkRtZnxAg7dyKpOmVNDbaul04J0jot0svViWagzCy5e7_39cF_reuIqCUAiWchodVgs-UpW51Mhn8k5pYKa6jiUKsHoIRyxuYI64DtTKy7zDyqrxMQWaoac4ChobAYVQ5ON-dZJQsOazEAGrD9nnTGDrC59-z2vxupHHg5FZunN2bJd9g56pwQTCi9hFXAWORDNlsKvsjkwRIrnnx9P5A/4l8/DYzXM6UhTMSjsFlzBG0kgA/h6/h001.ttBQDHp1sbIfWBuRdN6FAaZCUrGbyuhO9rq9iWITNB0" style="text-decoration:none;color:#ffffff;background:#006ce4;font-size:16px;line-height:24px;font-weight:500;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;border-radius:4px;width:auto;border:1px solid transparent;display:inline-block;text-align:center" target="_blank" rel="noreferrer"><span><!--[if mso | IE]>\r\n          <i style="letter-spacing: 16px; mso-font-width: -100%; mso-text-raise: 24px" hidden>&nbsp;</i>\r\n        <![endif]--></span><span style="display:inline-block;mso-text-raise:12px;padding:12px 16px"><span>Réserver avec mon code</span></span><span><!--[if mso | IE]>\r\n          <i style="letter-spacing: 16px; mso-font-width: -100%; mso-text-raise: 24px" hidden>&nbsp;</i>\r\n        <![endif]--></span></a></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:24px 16px 8px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="m-block m-w-full" style="width:624px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:inherit;font-size:16px;line-height:24px;font-weight:700;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Conditions générales d'utilisation</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="" style="width:16px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:20px;line-height:28px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>•</span></span></div></td></tr></tbody></table></td><td class="" width="8" height="8" valign="top" style="font-size:0"> </td><td class="m-w-auto" style="width:600px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Afin de bénéficier de cette récompense, vous devez dépenser au moins € 100 sur une seule réservation</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="" style="width:16px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:20px;line-height:28px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>•</span></span></div></td></tr></tbody></table></td><td class="" width="8" height="8" valign="top" style="font-size:0"> </td><td class="m-w-auto" style="width:600px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Le montant maximum de la récompense s'élève à € 100</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="" style="width:16px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:20px;line-height:28px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>•</span></span></div></td></tr></tbody></table></td><td class="" width="8" height="8" valign="top" style="font-size:0"> </td><td class="m-w-auto" style="width:600px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Ce code peut être utilisé une seule fois</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="" style="width:16px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:20px;line-height:28px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>•</span></span></div></td></tr></tbody></table></td><td class="" width="8" height="8" valign="top" style="font-size:0"> </td><td class="m-w-auto" style="width:600px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Ce code doit être appliqué avant la réservation et ne peut pas être appliqué à une réservation existante</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="" style="width:16px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:20px;line-height:28px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>•</span></span></div></td></tr></tbody></table></td><td class="" width="8" height="8" valign="top" style="font-size:0"> </td><td class="m-w-auto" style="width:600px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>La récompense vous sera versée sous forme de Crédit de Voyage dans votre Portefeuille Booking.com</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="" style="width:16px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:20px;line-height:28px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>•</span></span></div></td></tr></tbody></table></td><td class="" width="8" height="8" valign="top" style="font-size:0"> </td><td class="m-w-auto" style="width:600px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Le Crédit de Voyage sera ajouté à votre Portefeuille environ 2 semaines après votre départ de l'établissement</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="" style="width:16px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:20px;line-height:28px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>•</span></span></div></td></tr></tbody></table></td><td class="" width="8" height="8" valign="top" style="font-size:0"> </td><td class="m-w-auto" style="width:600px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span><span style="color: #6B6B6B">Le Crédit de Voyage sera valable pendant 1 an à compter de la date à laquelle il aura été ajouté à votre Portefeuille.</span></span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 0px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="" style="width:16px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:20px;line-height:28px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>•</span></span></div></td></tr></tbody></table></td><td class="" width="8" height="8" valign="top" style="font-size:0"> </td><td class="m-w-auto" style="width:600px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Cette promotion expire le 7 novembre 2025</span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr class=""><td style="background-color:#ffffff;padding:0px 16px 48px 16px"><table class="m-w-full" width="624" role="presentation" cellPadding="0" cellSpacing="0" border="0" align="center" dir="ltr"><tbody><tr><td class="" style="width:16px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:center;line-height:1px" align="center"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:20px;line-height:28px;font-weight:700;font-family:&quot;Avenir Next&quot;, BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>•</span></span></div></td></tr></tbody></table></td><td class="" width="8" height="8" valign="top" style="font-size:0"> </td><td class="m-w-auto" style="width:600px" valign="top"><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="" style="text-align:left;line-height:1px" align="left"><div style="display:inline-block;vertical-align:top"><span style="margin:0;color:#595959;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"><span>Pour plus d'informations, consultez l'intégralité des <a href="https://link.sg.booking.com/ss/c/u001.VL1ubDU2Gghhb8I0Y67cRHfnQySdyIkpI7XPDKq6fiUvYppnWlqTRWpIkT05RrY_XVWFYuoZ8N-k99S1gIFsRyixPVqh0F3ojvSlItzW3hRrfh5F7_sJRIHLI_rSmOhAz-oYQTuJZ4XzKwrBj0lcpcx9Osn90yqdlpSu9-XN5ReOQ_dMxSNYS1fFdusgTpH-2Ro-FL6cf3Zt-UUzsU6TK5Vme6YN5Y2R5RcsPb6XF4qfCCtH0RiBGIyDebY5ogDJy52gfqHwoRbLNhYADUVZDg/4l8/DYzXM6UhTMSjsFlzBG0kgA/h7/h001.zNDBK2ejnJBAOgBGoPrEG-VOC6pk9jC1a1x9n1YOa0Y" target="_blank" rel="noreferrer" style="font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;text-decoration:underline;color:#006ce4;;">Conditions générales d'utilisation</a> et la <a href="https://link.sg.booking.com/ss/c/u001.VL1ubDU2Gghhb8I0Y67cRHfnQySdyIkpI7XPDKq6fiVKTJ9a9BDCpkjXQSsJWzi-dHNYZCI48lvBHYv-ceruwMR4z9YVxuXc227_rNV15lAVWBUEXesaY2TjMi0puDj9-V8os38USg1mEFaoDtR3-WD9Vvahpotabxf-Yss8xdP4N503Me8KwBt3vitQ2pQlg8Nxz0980Ks7IeXREVaKXNQEZFeR8YKac-AbJvUqjnNrN-adnRn80NP4K24jlMoL/4l8/DYzXM6UhTMSjsFlzBG0kgA/h8/h001.275ws9M-xgDGClkUo8_DKTf0HxwMDOlSxhIyN4gC2XU" target="_blank" rel="noreferrer" style="font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;text-decoration:underline;color:#006ce4;;">FAQ</a></span></span></div></td></tr></tbody></table></td></tr></tbody></table></td></tr><tr dir="ltr"><td><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td style="background-color:#f5f5f5;border-bottom:1px solid #e7e7e7;border-top:1px solid #e7e7e7;color:#1a1a1a;padding-top:48px;padding-bottom:48px;padding-left:16px;padding-right:16px"><div><!--[if mso | IE]>\r\n<table align="center" border="0" cellspacing="0" cellpadding="0" width="624" role="presentation">\r\n<tbody><tr><td valign="top" width="624">\r\n<![endif]--></div><table align="center" border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%" style="max-width:624px"><tbody><tr><td><table border="0" cellPadding="0" cellSpacing="0" role="presentation" width="100%"><tbody><tr><td class="links-black" style="padding-bottom:24px"><div style="margin:0;color:inherit;font-size:16px;line-height:24px;font-weight:700;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif">Booking.com</div></td></tr><tr><td style="padding-bottom:24px"><address class="links-black" style="font-style:normal"><div style="margin:0;color:inherit;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;padding-bottom:4px">Oosterdokskade 163</div><div style="margin:0;color:inherit;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;padding-bottom:4px">1011 DL Amsterdam</div><div style="margin:0;color:inherit;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif">Pays-Bas</div></address></td></tr><tr><td style="padding-bottom:24px"><hr style="height:1px;background:#e7e7e7;border:0;margin:0"/></td></tr><tr><td style="padding-bottom:24px"><a href="https://link.sg.booking.com/ss/c/u001.VL1ubDU2Gghhb8I0Y67cRKA7D_oZP-nBJl-xtWUaTl17wwmFW-dnp81K59Ur8JkOuotvSJYB_U3ZzcmXIUSoEfDRT32NeCjl9V4YB555rhlMMwMNM_WkTYzugVnJG9c9S9PPDiDMzV0HUKREXG319Fuo897Yg1baFcac56bI3tbVBw7Jx044Eb695jt19Shn0ksFA6OHRJfPyqQ4n-ycm8WXrRy16ODY1JbaKeIZNF7ogtyMbq7XlYOu7bT-hWwy8-v6kGVF5ScCt-J9zYpdf3O_sZLctRCYbXli4396EJPVMOnQ8AUIM7UqOnpxKL8b/4l8/DYzXM6UhTMSjsFlzBG0kgA/h9/h001.e_Ls0PfV8EiKJtk9iy2yVfH1icsnjQ4RqJ_aY97D2Gc" style="text-decoration:none;color:#1a1a1a;display:inline" target="_blank" rel="noreferrer"><span style="margin:0;color:inherit;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif">Gérer les abonnements par e-mail</span></a></td></tr><tr><td style="padding-bottom:24px"><a href="https://link.sg.booking.com/ss/c/u001.VL1ubDU2Gghhb8I0Y67cRKA7D_oZP-nBJl-xtWUaTl17wwmFW-dnp81K59Ur8JkOuotvSJYB_U3ZzcmXIUSoEfDRT32NeCjl9V4YB555rhlMMwMNM_WkTYzugVnJG9c9S9PPDiDMzV0HUKREXG319Fuo897Yg1baFcac56bI3ta7IdzM-8dnGlyZEPRvOxwRtFjftgAjfnZd1yWPOzdwMpFeehJEYdNBnK_GzGr5WC4cKfEJiiG90yGKYqK6aIK6uP5GtUhF6iE_szVWUDn8eS_YNIQwvx-x-OOTM5J_wWjUTkijvyM2WWrKWrSPDafGihYNKhdzRuwB1uEpJyq0_-5FevWlBY4QPyWuYfwBY-w/4l8/DYzXM6UhTMSjsFlzBG0kgA/h10/h001.qqjIEcmxt0tTTaXyFPhvAwlhPdjLy781lPaSG_mMVSY" style="text-decoration:none;color:#1a1a1a;display:inline" target="_blank" rel="noreferrer"><span style="margin:0;color:inherit;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif">Se désabonner de cet e-mail</span></a></td></tr><tr><td style="padding-bottom:24px"><a href="https://link.sg.booking.com/ss/c/u001.VL1ubDU2Gghhb8I0Y67cRKA7D_oZP-nBJl-xtWUaTl17wwmFW-dnp81K59Ur8JkOuotvSJYB_U3ZzcmXIUSoEfDRT32NeCjl9V4YB555rhlMMwMNM_WkTYzugVnJG9c9S9PPDiDMzV0HUKREXG319Fuo897Yg1baFcac56bI3tZnt7A-59F7nlCGbs1-60tVfsheLgWZJhjyk8LgXPqKjn2BJ9RPdwAu9oAnSBs35gDKE8aN7MIoqKDkTUvPSEsVWimJR6FFFU8kIhQIlnjEQXPIeCl_zrFOCLvpLwBciSeHopDJu28PuOPbghBUWYbV-7ygHeIwL_cEtHAe6Yg1FQ/4l8/DYzXM6UhTMSjsFlzBG0kgA/h11/h001.fzn_mJ0ZkeRxdGbwu0Rd3abcAoY6LjVRhJFRFS9VrwA" style="text-decoration:none;color:#1a1a1a;display:inline" target="_blank" rel="noreferrer"><span style="margin:0;color:inherit;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif">Me désabonner de tous les e-mails marketing</span></a></td></tr><tr><td style="padding-bottom:24px"><a href="https://link.sg.booking.com/ss/c/u001.VL1ubDU2Gghhb8I0Y67cRHfnQySdyIkpI7XPDKq6fiW3FAzIhCiLWVRi6Mspa-BfIUKAs1d8BXcnZ7QIt285ds4bZWz0cAVtgzcXeX5TYD6LaSaUjIFYv5U_IKmSYH2wInEbvcY1rSXWDfxEY6qAPikH4sbDIV2tlmzPXck-Gfd6IbfktVPLMbnSX2RCmBMC/4l8/DYzXM6UhTMSjsFlzBG0kgA/h12/h001.JaM-w34txOvPmXKjPgse4bT8XmuHspjTir6QiUCfLXk" style="text-decoration:none;color:#1a1a1a;display:inline" target="_blank" rel="noreferrer"><span style="margin:0;color:inherit;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif">Service Clients</span></a></td></tr><tr><td style="padding-bottom:24px"><a href="https://link.sg.booking.com/ss/c/u001.VL1ubDU2Gghhb8I0Y67cRHfnQySdyIkpI7XPDKq6fiV5g_iE5-Gmc9Zby2-oGIbpvxvr_Rcx7ysUjT-_Q25Sv8EXi-noK6P8zveriNeDDtFSvJ9l2-wJA4vDbq0Qlq-zUkNfEvFxbXPfzXvo-AM9F-TgP3hDwr5cL0RvyfpS1-9c9R2Mxoa4iVDnS_gvYbnbIps4stXxIfxAVYkwZHvAig/4l8/DYzXM6UhTMSjsFlzBG0kgA/h13/h001.2I4e0dC4l1GDL4iioNQJ_pi5azGxa2gRplwHSb4WP6I" style="text-decoration:none;color:#1a1a1a;display:inline" target="_blank" rel="noreferrer"><span style="margin:0;color:inherit;font-size:14px;line-height:20px;font-weight:400;font-family:BlinkMacSystemFont, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif">Charte de confidentialité</span></a></td></tr></tbody></table></td></tr></tbody></table><div><!--[if mso | IE]>\r\n</td></tr></tbody></table>\r\n<![endif]--></div></td></tr></tbody></table></td></tr></tbody></table></div>\r\n        </body>\r\n      </html>\r\n	ROUTINE	\N	[]	\N	t	t	2025-11-01 08:05:35+00	2025-11-01 10:48:38.924444+00	2025-11-01 10:48:38.922307+00	\N	\N	\N
2	19a3b00515cdb47a	19a3aff9cfab9ba3	Gregori Bonetto <gregori.bonetto@gmail.com>	\N	3/3 Gregori Bonetto	bonjour;  je ne sais pas ce qu'il s'est passé, j'ai de l'eau de partout\r\ndans la maison.\r\nQui dois je contacter ?\r\n	URGENT	\N	[]	\N	t	t	2025-10-31 16:01:06+00	2025-11-01 12:08:24.050612+00	2025-11-01 12:08:24.011652+00	\N	\N	\N
3	19a3aff6b97ad8f7	19a3afe369dbb97e	Gregori Bonetto <gregori.bonetto@gmail.com>	\N	2/3 Gregori bonetto 86 Av Tasigny	Bonjour; j'ai mon compteur électrique qui est cassé je ne sais pas quoi\r\nfaire. Ca sent une odeur bizarre et j'ai l'impression qu'il y a de la\r\nfumée.\r\n	URGENT	\N	[]	\N	t	t	2025-10-31 16:00:08+00	2025-11-01 12:08:24.071916+00	2025-11-01 12:08:24.011652+00	\N	\N	\N
4	19a3afdd99b14b50	19a3afcf3bcae768	Gregori Bonetto <gregori.bonetto@gmail.com>	\N	1/3 degat des eaux chez moi	Bonjour, un tuyau a pété chez moi, j'ai besoin d'une intervention immédiate\r\nmerci.\r\n	URGENT	\N	[]	\N	t	t	2025-10-31 15:58:25+00	2025-11-01 12:08:24.07581+00	2025-11-01 12:08:24.011652+00	\N	\N	\N
5	19a3f3603a988075	19a3f3603a988075	"Anthropic, PBC" <invoice+statements@mail.anthropic.com>	\N	Your receipt from Anthropic, PBC #2667-6004-8950		ROUTINE	\N	[]	\N	t	t	2025-11-01 11:38:14+00	2025-11-01 12:08:24.079505+00	2025-11-01 12:08:24.011652+00	\N	\N	\N
6	19a3ea850b57697d	19a3ea850b57697d	SwissBorg <cyborg@swissborg.com>	\N	🧟 Ils sont toujours là, Gregori, aidez-nous à les combattre !	Les monstres ne sont pas partis. Mais certains Borgers ont déjà réclamé leurs \nrécompenses…\n\n\n\n\n\n\n\n\nStandard  Montez de niveau  <https://swissborg.com/wa/v1/profile> \n\n\n\n\n\n\nLe week-end, c’est fait pour chasser\n\n\n😱 Gregori, les monstres sont toujours en liberté.\n\n\nQuelques Borgers courageux ont déjà été récompensés pour leurs exploits, mais \nla malédiction d’Halloween n’est pas encore levée.\n\n\n\n\n\n\nTransformez vos BORG en armes et réclamez votre dû !\n\n\n\n\n\n🤔 Comment ça marche :\n\n\n\n1️⃣ Chassez les monstres en achetant n’importe quel montant de BORG \n<https://swissborg.com/wa/v1/marketplace/crypto/BORG>.\n\n\n\n2️⃣ Juste après chaque achat, vous saurez immédiatement si vous avez gagné, \ngrâce à une notification push et un message dans l’app.\n\n\n3️⃣ Plus vous achetez, plus vous avez de chances d’abattre un monstre.\n\n\n\n🎁 La récompense ?\n\n\nUne mise à niveau gratuite de votre Niveau de Fidélité pendant un mois, \njusqu’à Elite ! 😱\n\n\n\n\nDes récompenses si alléchantes que les monstres feront tout pour vous en \nempêcher.\n\n\n\n🗓️ Vous avez jusqu’au 2 novembre, à 23h59 CET.\n\n\n\nChaque achat de BORG est une nouvelle chance, soyez courageux, Gregori !\n\nPassez à l’attaque  <https://swissborg.com/wa/v1/marketplace/crypto/BORG>\n\n\n\n\n\n\n\nBon investissement,\n\nL'équipe SwissBorg\n\n\n\n\n(Les conditions générales s’appliquent) \n<https://swissborg.com/legal/general-terms-and-conditions>\n\n\n \n\n\n\nDes questions ? Visitez notre Centre d'Aide \n<https://help.swissborg.com/hc/fr-fr>\n\n\n\n\n\n\n Vous avez reçu cet e-mail parce que vous vous êtes inscrit à l'application \nSwissBorg. Si vous ne souhaitez plus recevoir d'e-mails, vous pouvez cliquer \nsur se  désinscrire  \n<http://links.swissborg.com/s/u/ZV6oeJYZyThvkcG7LIeTiwY6YcsWg4zrBe9IZvl3FKfh92UhkdoG8oB4Zu7sYdPNjlPgBK3eXaIY6tbuF1xe4ym2UK81D_UnYFdO3IHHsJmA00N1uQ6RnV3Bsmbmrdk5CccUr9tnwunPl7fZwAhaxgEG67FzYqZnFlL2ESmkUzda46Il08aA6sLc-6l6vKU/7CXjyoefn-PBruufns6g1RYwsdl72tDA/14>\n. \n\n\n\nSwissBorg Solutions OÜ \n\nPärnu mnt. 12, 10148 Tallinn, Estonie\n\n(opère l'application SwissBorg sous la licence estonienne FVT000326 et le \nnuméro d'enregistrement français E2022-034)\n\n\n\n Le contenu de cet e-mail ne doit pas être interprété comme une recommandation \nd'action. Toute personne souhaitant investir devrait rechercher son propre \nconseil financier professionnel indépendant avant de continuer.Cliquez ici \n<https://swissborg.com/legal/wealth-app-terms-of-use> pour plus d'informations.	ROUTINE	\N	[]	\N	t	t	2025-11-01 09:03:28+00	2025-11-01 12:08:24.083779+00	2025-11-01 12:08:24.011652+00	\N	\N	\N
7	19a3e928e43177cf	19a3e928e43177cf	celio <celio@email.celio.com>	\N	NOUVEAUTÉ : les pantalons thermiques	Nos doudounes face au froid | l'hiver n'a qu'a bien se tenir \r\n\r\n \r\n\r\n\r\n \r\n\r\n\r\n \r\n\r\n\r\n \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb13fbd8538b2cf4307886ec84a84ea5d44b515358f722e3901a9e00a86131cc8e7523766ee122882d6e12f8600e3f50d9a2890e528b5132564 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb151d1b9ff83ee88a281a818901d34594e6c59fec39b9d15e73cc06c1a4d6576e77b52eebc539a4741ec0479f40279ffb741122972ff8cebc5 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb14e0020af12ab1acafd5569db5ea8093c61cdf76f233edb01eb69e095e3994eedc7985dc7e16dfd423a33ae7fa477bae0f5bc1ed03509399b \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb14e0020af12ab1acafd5569db5ea8093c61cdf76f233edb01eb69e095e3994eedc7985dc7e16dfd423a33ae7fa477bae0f5bc1ed03509399b \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb14e0020af12ab1acafd5569db5ea8093c61cdf76f233edb01eb69e095e3994eedc7985dc7e16dfd423a33ae7fa477bae0f5bc1ed03509399b \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb14e0020af12ab1acafd5569db5ea8093c61cdf76f233edb01eb69e095e3994eedc7985dc7e16dfd423a33ae7fa477bae0f5bc1ed03509399b \r\n vos pantalons thermiques du quotidien.  \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb14e0020af12ab1acafd5569db5ea8093c61cdf76f233edb01eb69e095e3994eedc7985dc7e16dfd423a33ae7fa477bae0f5bc1ed03509399b \r\n D&#xE9;couvrez notre collection de pantalons thermiques, con&#xE7;ue pour vous offrir une chaleur maximale et un effet enveloppant.  \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb14e0020af12ab1acafd5569db5ea8093c61cdf76f233edb01eb69e095e3994eedc7985dc7e16dfd423a33ae7fa477bae0f5bc1ed03509399b \r\n\r\nd&#xE9;couvrir le niveau 3\r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1e1ca9828a030e72dfbe3ae6f12b730063a9a89bb9bca6843d0f6e853a55db3c8bce8a111a5317af929d4b013c94b373456244c0ab33e148f \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1a35acca11ffeb478d41c02d6888eafc70c2fab0545fcaa707f4f17abd165486c47a00669f75a9c5ba0672ee8c48785e6bda88b3330d0db2a \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb14fc00b614e50eff6115fe77df30c1c676ebd3f77d24480b09adc2e92612e93c50ac6f2547eaee29e327473a95fc648a62532a55bba20545a \r\n\r\nvoir le niveau 3\r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1736af518f10987c84f37ef4173efb72de6dd2c8bc54ab72d4b6cfeebdb5918721529a1b11e65821f1942300fd3fc3cb4bec0178c0fe6fa27 \r\n et pour compl&#xE9;ter...  \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1736af518f10987c84f37ef4173efb72de6dd2c8bc54ab72d4b6cfeebdb5918721529a1b11e65821f1942300fd3fc3cb4bec0178c0fe6fa27 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1736af518f10987c84f37ef4173efb72de6dd2c8bc54ab72d4b6cfeebdb5918721529a1b11e65821f1942300fd3fc3cb4bec0178c0fe6fa27 \r\n\r\nd&#xE9;couvrir les pulls\r\n\r\n\r\n\r\n\r\n \r\n\r\n\r\n \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1b361996d934a3f76e2f9d05650d5e5e1185941e27fd17caa16dc0648dc302b11d0445694efb900c5389702a581c71c2f \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1b361996d934a3f76e2f9d05650d5e5e1185941e27fd17caa16dc0648dc302b11d0445694efb900c5389702a581c71c2f \r\n Gregori Bonetto  \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1b361996d934a3f76e2f9d05650d5e5e1185941e27fd17caa16dc0648dc302b11d0445694efb900c5389702a581c71c2f \r\n ID client : 202361793  \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1b361996d934a3f76e2f9d05650d5e5e1185941e27fd17caa16dc0648dc302b11d0445694efb900c5389702a581c71c2f \r\n &#xEA;tre fid&#xE8;le &#xE0; celio, &#xE7;a rapporte : bons d'achat, &#xE9;v&#xE8;nements, ventes priv&#xE9;es...  \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1b361996d934a3f76e2f9d05650d5e5e1185941e27fd17caa16dc0648dc302b11d0445694efb900c5389702a581c71c2f \r\n\r\nd&#xE9;couvrir be+\r\n\r\n\r\n\r\n\r\n \r\n &zwnj; \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1ebcc59e69bbcbd992ea1a7ba2da9160f769277f1450d65a3442a33fced22b2e58e9981de3dc31b57347179a218a5a1f0a1dec7fcaab58969 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1ebcc59e69bbcbd992ea1a7ba2da9160f769277f1450d65a3442a33fced22b2e58e9981de3dc31b57347179a218a5a1f0a1dec7fcaab58969 \r\n click & collect : retrait gratuit en 2h  \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1ebcc59e69bbcbd992ea1a7ba2da9160f769277f1450d65a3442a33fced22b2e58e9981de3dc31b57347179a218a5a1f0a1dec7fcaab58969 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1ebcc59e69bbcbd992ea1a7ba2da9160f769277f1450d65a3442a33fced22b2e58e9981de3dc31b57347179a218a5a1f0a1dec7fcaab58969 \r\n retours gratuits en magasin  \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1ebcc59e69bbcbd992ea1a7ba2da9160f769277f1450d65a3442a33fced22b2e58e9981de3dc31b57347179a218a5a1f0a1dec7fcaab58969 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1ebcc59e69bbcbd992ea1a7ba2da9160f769277f1450d65a3442a33fced22b2e58e9981de3dc31b57347179a218a5a1f0a1dec7fcaab58969 \r\n livraison offerte \r\nd&#xE8;s 49&#x20AC; d'achat \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1ebcc59e69bbcbd992ea1a7ba2da9160f769277f1450d65a3442a33fced22b2e58e9981de3dc31b57347179a218a5a1f0a1dec7fcaab58969 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1ebcc59e69bbcbd992ea1a7ba2da9160f769277f1450d65a3442a33fced22b2e58e9981de3dc31b57347179a218a5a1f0a1dec7fcaab58969 \r\n paiement s&#xE9;curis&#xE9; en 3x avec Alma  \r\n\r\n &zwnj; \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb17743cf558f264ae98820466cdf7b66436a59fc42b225316fa0b0a30465fd9f019a33189e8d43550561b120f61cea2bf0 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb14d800cde760fee2fbf01c871b1d68fb0b862a6e16fd5e0c19376ab27e17f8201a05f90c2ae31be959d0566444e5c1518 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb10acad108801360780c8d8223e8800700a9c9cf497c81311f1cbb29ca477fd40b51736fb2adf230586170e54cbeef4019 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1ec24b03817f82d74b0da783e897777de2a2480be6ff902eace98683b56078e2903be1a3081739d563300146d6923e5bf \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb105ffb1cd0770c3ea0fa9f393357ae776ff9c32b46bd336fb34a0711338dda621f3b1da41044c14ec9d2a11b6aed96daa \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1c91b2d52d2a59686c7daf47a482eda41b48ed256f02ddc5b5b5ee96145944d74ca8f2975a2fe3948625fe2e0c39f7162 \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1b3545d4efdafa6e18e84632d577324b1398c20272f11adfc73e29762daae727b20fcc5ba7dd106a6d4f57e8abda31fb1 \r\n\r\n &zwnj; \r\n\r\n\r\n\r\n \r\n\r\nhttps://view.email.celio.com/?qs=4b93953ba02ea61a60b2cfdad2a24d12809269371bb6669d5cb3eefcafd22849774c9727bd563f1d3535cf437f3ee5b8324c2c222ef9d83a997d0e94298c5145a5ab05b53a6f5c937aaf1812ba44daf933f348c9ef7cccca \r\n\r\nce message ne s&#x2019;affiche pas correctement ? consultez notre version en ligne\r\n\r\nVous recevez cet email car vous avez accept&#xE9;, en magasin ou en ligne, de recevoir des informations personnalis&#xE9;es par email de la part de celio. CELIO FRANCE est le responsable de ce traitement au sens du r&#xE8;glement (UE) 2016/679 du 27 Avril 2016. \r\n Voir les conditions g&#xE9;n&#xE9;rales du programme de fid&#xE9;lit&#xE9; \r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1f7f8171c7ae990fad45fafa50a7d266c32e8aa7dddcc155c182b13d5ffaa3818ef48815072783d98588e4942e0be11a8 \r\nici .\r\n\r\n*Niveau de chaleur bas&#xE9; sur une mesure de r&#xE9;sistance thermique r&#xE9;alis&#xE9;e selon la norme ISO 11092. Classification interne Celio \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb192369c9d837e690a8381b32c0472f6dd26f734cc36291f3f28f18b2143775b19f2387f30d8c94397a9b27ce6b449892229bfd99d0b2af941 \r\n Vous pouvez &#xE0; tout moment, choisir  d&#x2019;&#xEA;tre retir&#xE9; d&#xE9;finitivement de nos listes de diffusion. \r\n\r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1e45b11be9e73dc75a66fb3a751db46086f32eb5624b949c8b762fd2464bc4dba713a49893b044a93be8ad4db35e58b18858fde3d3786d97c \r\nContactez-nous  sur \r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb1e45b11be9e73dc75a66fb3a751db46086f32eb5624b949c8b762fd2464bc4dba713a49893b044a93be8ad4db35e58b18858fde3d3786d97c \r\ncelio.com/fr-fr/contactus  ou par courrier au Service client 21 rue Blanqui 93400 Saint-Ouen, France, pour exercer votre droit d&#x2019;acc&#xE8;s, de rectification, de portabilit&#xE9;, d&#x2019;effacement, de limitation du traitement et d&#x2019;opposition au traitement conform&#xE9;ment au r&#xE9;glement (UE) 2016/679. Pour plus d&#x2019;informations, consultez notre Politique relative aux donn&#xE9;es personnelles \r\nhttps://click.email.celio.com/?qs=dcd7d5187a8efdb113cf24be2ea713331d3db8f24d9c351f88cae39778f02a96e22bcd1fb02298f503a52b01632115c2798aca7f80c7d6237f201c3f87e02c46 \r\nici . Si vous rencontrez des probl&#xE8;mes avec le lien de d&#xE9;sabonnement, merci de vous rapprocher du service client.\r\n\r\n\r\n\r\n	ROUTINE	\N	[]	\N	t	t	2025-11-01 08:05:09+00	2025-11-01 12:08:24.089872+00	2025-11-01 12:08:24.011652+00	\N	\N	\N
8	19a3cf80c2a492a3	19a3cf80c2a492a3	Votre Assurance Maladie <assurance-maladie@info.ameli.fr>	\N	Information de paiement	Bonjour,\r\n\r\nVous avez reçu un nouveau message de l'Assurance Maladie. Pour le consulter, cliquez ici : https://statsndm.info.ameli.fr/m/IKWzVokYgGjW7ETMw2eEUdSG4QG8oPmGRJuAkmEOuqtEEDjEZmXiTR0fQtc2Y51vikYIqvu82yeiN0ptl0sBPZfrjKDOsm9hzqcbTZzvwLDBY2snhSjIcLgBBCmaYqq7Rh0pH5Kiz-i3GcuE4qvVvs9TKg4trbi34vbV_I3JXjmbNw== \r\n\r\nAvec toute notre attention,\r\n\r\nL'Assurance Maladie	ROUTINE	\N	[]	\N	t	t	2025-11-01 01:11:19+00	2025-11-01 12:08:24.0979+00	2025-11-01 12:08:24.011652+00	\N	\N	\N
9	19a3b3946b24a836	19a3b3946b24a836	"Nouvelle Énergie" <nepasrepondre@unenouvelleenergie.fr>	\N	Afuera la réglementation !	Voir ce courriel dans votre navigateur (https://mailchi.mp/unenouvelleenergie/newsletter-ne-31102025?e=86ce1b05fc)\r\nhttps://unenouvelleenergie.fr\r\n\r\n\r\n** David Lisnard sur France Inter : « Afuera la réglementation ! »\r\n------------------------------------------------------------\r\n\r\nInvité d’Alexandra Bensaïd dans La Grande Matinale de France Inter, mercredi 29 octobre 2025, David Lisnard a livré une analyse sans détour de la situation politique et économique française, appelant à une rupture profonde avec le modèle actuel.\r\nEn savoir plus (https://www.unenouvelleenergie.fr/david-lisnard-sur-france-inter-afuera-la-reglementation/)\r\n\r\n\r\n** Des travaux d’intérêt général pour responsabiliser les jeunes auteurs de dégradations\r\n------------------------------------------------------------\r\n\r\nÀ Cannes, la sanction rime avec responsabilité. Deux adolescents ayant dégradé des espaces verts ont récemment été interpellés par la police municipale, puis convoqués en mairie avec leurs parents. Sous la décision de David Lisnard, ils ont été sanctionnés par des travaux d’intérêt général (TIG) durant leurs vacances scolaires.\r\nLire la suite (https://www.unenouvelleenergie.fr/des-travaux-dinteret-general-pour-responsabiliser-les-jeunes-auteurs-de-degradations/)\r\n\r\n\r\n** Le Tour de France Nouvelle Énergie est lancé !\r\n------------------------------------------------------------\r\n\r\nNouvelle Énergie a lancé son Tour de France avec une première étape à Dammarie-les-Lys, en Seine-et-Marne. Une belle soirée d’échanges et de mobilisation autour du projet porté par David Lisnard, en présence de Romain Marsily, directeur général de Nouvelle Énergie, et du sénateur Stéphane Piednoir.\r\nLire la suite (https://www.unenouvelleenergie.fr/le-tour-de-france-nouvelle-energie-est-lance/)\r\n\r\n\r\n** Par Romain Marsily,\r\n------------------------------------------------------------\r\n\r\nDirecteur général de Nouvelle Énergie\r\n\r\n« Porter le combat, partout !\r\n\r\nPlus que jamais, la France a besoin du projet libéral, sécuritaire et éducatif que porte David Lisnard. Face au déclin organisé par des décennies de social-étatisme, nous devons faire gagner nos idées.\r\n\r\nCela suppose de mener partout le combat intellectuel : sur les réseaux sociaux, sur le terrain, dans chaque débat. Partout, déconstruire les dogmes socialistes qui freinent le pays. Partout, transmettre avec enthousiasme notre projet : retrouver la prospérité, restaurer l’autorité, reconstruire l’école, redonner sens à la liberté et à la justice, faire de la France une superpuissance éducative, scientifique et culturelle. C’est un enjeu de concorde nationale et de souveraineté réelle.\r\n\r\nNous seuls portons ce projet d’espérance. Soyons-en fiers, soyons offensifs, faisons-le rayonner.\r\n\r\nLes adhérents, véritables ambassadeurs de Nouvelle Énergie, sont essentiels à cette bataille politique dans laquelle les échanges sont primordiaux. Le Tour de France de Nouvelle Énergie, dont j’ai eu le plaisir de coanimer la première étape à Dammarie-les-Lys, en Seine-et-Marne, cette semaine, en témoigne. J’y ai senti une détermination profonde à redresser le pays. Transformons cette détermination en élan vers la victoire. Cela ne dépend que de nous tous. »\r\n\r\n\r\n** « La retraite par capitalisation, n’est-ce pas trop risqué ? On peut tout perdre avec les aléas du marché. »\r\n------------------------------------------------------------\r\n\r\nAvec la capitalisation, les pensions sont toujours plus élevées qu’avec la répartition. De plus, celles-ci sont toujours garanties, quels que soient les aléas du marché, grâce à la diversité des placements et à leurs rendements élevés. David Lisnard propose par ailleurs de conserver une partie de la répartition afin de garantir une sécurité supplémentaire. La répartition ne permet pas de garantir la pérennité des pensions ni leur niveau, en raison du déclin démographique : il y a de moins en moins de travailleurs pour payer les pensions des retraités qui sont de plus en plus nombreux. Le système actuel, gravement déficitaire, est devenu un fardeau pour les finances publiques, puisque l’Etat doit chaque année mettre la main à la poche pour le renflouer. Le seul moyen de conserver le système actuel serait de repousser continuellement l’âge de départ à la retraite ou d’augmenter le montant des cotisations, ce qui n’est pas souhaitable. Avec la capitalisation, chacun se con\r\nstitue librement son propre capital, peut partir à l’âge qui le souhaite et avoir des revenus bien plus élevés.\r\n\r\n\r\n** Olivier Paz\r\n------------------------------------------------------------\r\n\r\n\r\n** Maire Nouvelle Énergie de Merville-Franceville\r\n------------------------------------------------------------\r\n\r\nOlivier Paz est le maire Nouvelle Énergie de Merville-Franceville, dans le Calvados, commune littorale marquée par l’histoire du Débarquement. Présent le 5 décembre 1976 Porte de Versailles pour la création du RPR, il a depuis adhéré sans discontinuer au mouvement gaulliste. « Le hold-up de l’élection présidentielle de 2017 m’a laissé un goût tellement amer que j’ai pensé être dégoûté à jamais de la politique » explique-t-il. « Fort heureusement, j’ai découvert David Lisnard en 2019 et j’ai adhéré à Nouvelle Énergie dès 2020, tant les convictions de cet élu, sa constance, sa vision, la façon dont il réhabilitait les mots : dignité, responsabilité, liberté, me parlait. Aujourd’hui, alors qu’autour de nous tout se délite à grande vitesse, je suis persuadé qu’il est l’homme de la situation, celui qui saura rencontrer les français, les convaincre, leur rendre leur dignité et rendre sa grandeur à la France. »\r\nhttps://soutenir.unenouvelleenergie.fr/adhesion\r\n\r\n\r\n** David Lisnard a lancé une consultation nationale (https://www.unenouvelleenergie.fr/consultation-bureaucratie/) pour recueillir les témoignages des Français sur la bureaucratie qu'ils affrontent dans leur quotidien. Chaque semaine, nous vous partageons un témoignage emblématique.\r\n------------------------------------------------------------\r\n\r\n« Je dirige un supermarché en Picardie : nous avons subi un contrôle sur les origines des fruits et légumes. Nous indiquions “origine Aisne” au lieu de “Origine France” : non conforme ! Résultat : dix mois de procédures, trois dossiers administratifs différents et 9 000 € de frais. En France, il faut être riche et patient pour travailler… »\r\nDavid, Oise\r\nParticiper à la consultation (https://www.unenouvelleenergie.fr/consultation-bureaucratie/)\r\nhttps://www.unenouvelleenergie.fr/consultation-bureaucratie/\r\nhttps://x.com/davidlisnard/status/1983102937363587199\r\nDavid Lisnard\r\n@davidlisnard\r\nX (https://x.com/davidlisnard/status/1983102937363587199)\r\nÀ la question : comment éviter l’exil de l’Urss, la réponse du bloc soviétique fut le mur de Berlin contre les hommes libres.\r\nÀ la question : comment éviter l’exil fiscal de la France, la réponse de l’idéologue déguisé en économiste est le bouclier contre les contribuables.\r\nOr, la bonne réponse était : ne pas créer de régime liberticide et spoliateur.\r\nhttps://x.com/LCI/status/1982902331420103009\r\nLCI\r\n@LCI\r\n🗣 "Comment éviter l'exil fiscal ? Je propose que l'on crée un bouclier anti exil fiscal. Que les personnes redevables de l'impôt en resteraient redevables après un éventuel exil pendant 5 ou 10 ans." ➡ @gabriel_zucman sur LCI\r\nVoir le tweet (https://x.com/LCI/status/1982902331420103009)\r\n10:25 · 28 oct. 2025 · Voir sur X (https://x.com/davidlisnard/status/1983102937363587199)\r\nEn savoir plus (https://x.com/davidlisnard/status/1983102937363587199)\r\n\r\n\r\n** 📅 Agenda à venir\r\n------------------------------------------------------------\r\n\r\nRejoignez nos événements partout en France.\r\n04\r\nnov.\r\n2025\r\n\r\n\r\n** Apéritif des adhérents du Gard\r\n------------------------------------------------------------\r\n\r\nVilleneuve-lès-Avignon (Gard) • 19h\r\n\r\nMaison Bronzini, 74 rue de la République.\r\nEn savoir plus (https://www.unenouvelleenergie.fr/event/aperitif-des-adherents-du-gard/)\r\n06\r\nnov.\r\n2025\r\n\r\n\r\n** À la rencontre des Alésiens\r\n------------------------------------------------------------\r\n\r\nAlès (Gard) • 19h\r\n\r\nLieu transmis après inscription.\r\nEn savoir plus (https://www.unenouvelleenergie.fr/event/a-la-rencontre-des-alesiens/)\r\n13\r\nnov.\r\n2025\r\n\r\n\r\n** Réunion publique à Marseille avec David Lisnard\r\n------------------------------------------------------------\r\n\r\nMarseille (Bouches-du-Rhône) • 19h\r\n\r\nDomaine des Calanques, 229 route Léon Lachamp (13009). Inscription obligatoire.\r\nEn savoir plus (https://www.unenouvelleenergie.fr/event/__trashed/)\r\n13\r\nnov.\r\n2025\r\n\r\n\r\n** Soirée-débat avec Étienne Blanc\r\n------------------------------------------------------------\r\n\r\nMontauban (Tarn-et-Garonne)\r\nEn savoir plus (https://www.unenouvelleenergie.fr/event/soiree-debat-avec-etienne-blanc/)\r\n15\r\nnov.\r\n2025\r\n\r\n\r\n** Soirée d’échanges avec Yves d’Amécourt\r\n------------------------------------------------------------\r\n\r\nGaillac (Tarn) • 18h\r\nEn savoir plus (https://www.unenouvelleenergie.fr/event/soiree-dechanges-avec-yves-damecourt/)\r\n20\r\nnov.\r\n2025\r\n\r\n\r\n** Atelier sur l’éducation\r\n------------------------------------------------------------\r\n\r\nHegenheim (Haut-Rhin) • 18h45\r\nEn savoir plus (https://www.unenouvelleenergie.fr/event/atelier-sur-leducation/)\r\n22\r\nnov.\r\n2025\r\n\r\n\r\n** Conférence-débat sur l’école avec Lisa Hirsig\r\n------------------------------------------------------------\r\n\r\nStrasbourg (Bas-Rhin)\r\nEn savoir plus (https://www.unenouvelleenergie.fr/event/conference-debat-sur-lecole-avec-lisa-hirsig/)\r\n28\r\nnov.\r\n2025\r\n\r\n\r\n** Le Tour de France Nouvelle Énergie en Gironde\r\n------------------------------------------------------------\r\n\r\nSaint-Aubin-de-Médoc (Gironde) • 19h\r\nEn savoir plus (https://www.unenouvelleenergie.fr/event/le-tour-de-france-nouvelle-energie-en-gironde/)\r\n28\r\nnov.\r\n2025\r\n\r\n\r\n** Soirée-débat avec Alexandra Martin et Hervé Novelli\r\n------------------------------------------------------------\r\n\r\nLe Muy (Var)\r\nEn savoir plus (https://www.unenouvelleenergie.fr/event/soiree-debat-avec-alexandra-martin-et-herve-novelli/)\r\n11\r\ndéc.\r\n2025\r\n\r\n\r\n** Réunion des adhérents\r\n------------------------------------------------------------\r\n\r\nEguisheim (Haut-Rhin)\r\nEn savoir plus (https://www.unenouvelleenergie.fr/event/reunion-des-adherents/)\r\nVoir tout l’agenda → (https://www.unenouvelleenergie.fr/agenda/)\r\nhttps://docs.google.com/forms/d/e/1FAIpQLSc2GfK0f2knIwMFB3mWdlhtbaK1MploG9BdhjiK2VHAHDhITA/viewform\r\nInscriptions (https://docs.google.com/forms/d/e/1FAIpQLSc2GfK0f2knIwMFB3mWdlhtbaK1MploG9BdhjiK2VHAHDhITA/viewform)\r\nhttps://soutenir.unenouvelleenergie.fr/adherer\r\nhttps://www.facebook.com/Nouv.Energie/\r\nhttps://instagram.com/@nouv_energie\r\nhttps://x.com/@Nouv_Energie\r\nhttps://tiktok.com/@nouvelle_energie\r\nhttps://www.unenouvelleenergie.fr\r\nhttps://youtube.com/@david_lisnard\r\nhttps://linkedin.com/company/nouvelle-energie-pour-la-france/\r\nhttps://wa.me/channel/0029Vb5f3G8IyPtKA5fSFY0Q\r\nhttps://t.me/nouvelleenergie\r\n\r\nCopyright (C) 2025 Nouvelle Énergie. Tous les droits sont réservés.\r\n\r\nVous souhaitez modifier la façon dont vous recevez ces e-mails ?\r\nVous pouvez\r\nmettre à jour vos préférences (https://unenouvelleenergie.us21.list-manage.com/profile?u=58ecf698369de0a25a2d78b6a&id=5926e1116c&e=86ce1b05fc&c=02c90fdc2a) or Se désabonner (https://unenouvelleenergie.us21.list-manage.com/unsubscribe?u=58ecf698369de0a25a2d78b6a&id=5926e1116c&t=b&e=86ce1b05fc&c=02c90fdc2a)	ROUTINE	\N	[]	\N	t	t	2025-10-31 17:00:55+00	2025-11-01 12:08:24.101131+00	2025-11-01 12:08:24.011652+00	\N	\N	\N
10	19a3f8dcb7f05e88	19a3f8dcb7f05e88	"Anthropic, PBC" <invoice+statements@mail.anthropic.com>	\N	Your receipt from Anthropic, PBC #2074-1912-4978		ROUTINE	\N	[{"filename": "Invoice-QGVOKOWC-0003.pdf", "mime_type": "application/pdf", "size": 32496, "attachment_id": "ANGjdJ8K9yerRqqkBATaKlzJ6ei1yo_tEfSPUxgazpLk84AsezOIZcRmjJzFhR79gxXset74-o_Gqx6uV-Kf9ozwmUbBHILBZW8ew1m9pHcwtbszP2InFMV7G3SFSUH1WffwoJhDVcX_hZ59x2LqO6q48di5SpAZ9CEkhV4YklgLMTNyE-ralznCSGOmUdBJraYQlPwBsVrfaUoZAQKaDKMJRJf1DxyiC3Ngeneh_0GQkdWM5jVSc-NQsRzN5cMpm7aMbClqETEqP-Y39jJcm8GPgP6EGs951aIvI7UvlyfVke3Vwt8QnkbD6697-NkEej7GisfhrBrIoMObxEASjrP0MUDiLI2eqCOUd-CEcUG1aMgQ3chrENlIWU149sJwdVKlU1IbaBoc-DGSiykv"}, {"filename": "Receipt-2074-1912-4978.pdf", "mime_type": "application/pdf", "size": 32445, "attachment_id": "ANGjdJ-69CvuG3zCWMz8pUqto55GcVw6cowST59WiTFjvc1LcVww1HVTWNTDMqD1sC_lxETs4IEvShzt5zlnO7QaXVwu3ofCe2y5R4EMbMnwrbYB1xl0Jnv7F9axYMQvYBLFy25jUuxNWGzwo2ibNMa0p4C5rzzXrzGzEidb-gKN7xKtxDssWYsPWblj_INTQLQeejNh5oaROAaM-qH9-EGSOavonzR2SKzzndLFX63rRXQV6K5c0OFR0Pbht9_Uik05n0mxBXbVIy9F4zB4zwFColvflMHpLQx-gRqSlSqSy4IvK5vSxNi53qCcCjidJi1iSmUr_84kQfhB7NZA8tyYoOn3KmdNEJzve0rQEmoKNBwzTJVvDo0hBhGfFjNtLUy1lO3YA6XPyRvMiUWb"}]	\N	t	t	2025-11-01 13:14:08+00	2025-11-01 15:28:41.30411+00	2025-11-01 15:28:41.295962+00	\N	\N	\N
11	19a3fc359c827235	19a3fc2e6e0ef606	Gregori Bonetto <gregori.bonetto@gmail.com>	\N	facture	bonjour, je vous transmet la facture que je devais vous fournier pour la\r\nderniere intervention du plombier a mon adresse\r\n	ROUTINE	\N	[]	\N	t	t	2025-11-01 14:12:37+00	2025-11-01 16:20:56.863575+00	2025-11-01 16:20:56.860496+00	\N	\N	\N
12	19a402e39de46e69	19a402e39de46e69	"Anthropic, PBC" <invoice+statements@mail.anthropic.com>	\N	Your receipt from Anthropic, PBC #2356-8696-3339		ROUTINE	\N	[{"filename": "Invoice-QGVOKOWC-0005.pdf", "mime_type": "application/pdf", "size": 32359, "attachment_id": "ANGjdJ9DABtPcR6EF4VlGhvx5BLwHcH46vnXSkJLJAH7Sej2Pdl_qlM7RlgLqlyuIH5R1pXs2DSjrqvlOIYXdi362p0kjUlhX3I76Druk19sVeQbGVxnczgA9BsSUslh3DgNW8XRSItwv1w2rp9yIyGPPSxIGsDANKFkjOR2pobOBax-aoiSml-J6ErXyKOCAKtb27mTi6wpRwjSyToC4SPi3xKy5vI_hgW1F-DECbElnBmuj-H3sIpQxkvaQiat_jGuc5GnvY4vQyjUp7lTp1T--VOHgOxwzOyFrILtAVB1t_e6IBS-viNjqxHqONhv8J3P9XUAB3Z8C3POBnc2zf8h10HfKPDxQbgOH1HmYpRvHMXZTJ0I9q5o5V06aViqc-lQQDgfWZ7vGZRzAm4P"}, {"filename": "Receipt-2356-8696-3339.pdf", "mime_type": "application/pdf", "size": 32291, "attachment_id": "ANGjdJ-g7m5H7K8GWSVHPQglsq2H_Zf6yROguuiwRDsUpj9PgD1heVSsm-2CZzYQXr4dmAqXg1oPmvBBn0QfNEvQ5llKNHsBjjkheR8xUdea7s4YlA7unv0ykM5oVmygwxT691LR-FfiyVRjzmsbHk8r58ayLjC8OpTNvClKKdoDEyyb--7POhjYGSZjxroxC3UXNzUMMXLO7lK8444krSbJWpN0kkUWnm0IsKsV0yOUni7hcEMW-YBIobCCzdkFdIzTKjttirJcj_OehuRDYx8IocbsxYP4IdqfNxw4hzTnPXzE1gdPZtb49d39AN6QCztMAu6uZLF7FCDji_nEyJ05dHuZl5cBdB7beIec52-_tfkprSRuHX8sN20IO2B9W86A2zVT7MVIu1pYM7Qp"}]	\N	t	t	2025-11-01 16:09:21+00	2025-11-01 16:28:38.492733+00	2025-11-01 16:28:38.48788+00	\N	\N	\N
13	19a3fafe04bb0449	19a3fafe04bb0449	"Anthropic, PBC" <invoice+statements@mail.anthropic.com>	\N	Your receipt from Anthropic, PBC #2116-9846-9748		ROUTINE	\N	[{"filename": "Invoice-QGVOKOWC-0004.pdf", "mime_type": "application/pdf", "size": 32224, "attachment_id": "ANGjdJ9oTjdRURzn_gF87wOnZPULCVK5pBCJ_Li8ISEXa518hY6U0CXimMaBMXEwskZXdYXsmRwYaZGB2qP3KgEHtthIi0IkJTttbzq_dAWjoIb6PJwIN4UcVNI45lIFSutAUudmMkbowaEDRGwDL9X03cNKWJYAKTtuxykM1BozFGV_Qsba02K_UrY6_KqEa7x2nnK7K1wr3uHTUDymPe7P_imN4EDK_6gYrd01TX36SbCa5nKfOSU5NgUbtRTfFht9COT4NGyplVVX6JpMBe2MJnH9iSIjc63pPnm4YR59cTIwTatrT7Y_4I_jkD__NZnQBBNKixEzHnW32H8vYCJBwuntlHXMIMKkr79lm2tV1sBi6ZLud7-li6hBSOYQqCK5P477p-SxJhBIQdqG"}, {"filename": "Receipt-2116-9846-9748.pdf", "mime_type": "application/pdf", "size": 32168, "attachment_id": "ANGjdJ80_bypft6dP0UH8hFfqftRpj4TT7-FksNZLzGZwbqD747phGNknIrh_a_YlhRkrxB0N4oAITkj8CujOjGIZ-is98S__uWcKTqjS8JQCcbdUPhGH8OlG6e9wYl03ykVtZ3LbYYPMF1O6qt_F1tCuHExmf29N9ndl8oTNEqent_LgrrGOjYJZaHbmLSyxGaznFv2oM6wvZTaOs6HPS0xGHccjjM4UJ0HdbSEZpMKRCKh9t7zjHQMiN6oyc3QBQNhAp7fOIYfBv2vdw7dozkATcpCeSLhLi1WX8yJ7HeOlOz0upP7YbCA8NPc-Cnkg0qJ9mK6vBFnd3tu5x_VJR5ra-R5qpWDT2HUoGAeBC4024-TE6kn74xJChso7cJ_v9UrjdreJdbc_xjvn6YU"}]	\N	t	t	2025-11-01 13:51:21+00	2025-11-01 17:42:27.22535+00	2025-11-01 17:42:27.223379+00	\N	\N	\N
\.


--
-- Data for Name: professionnels; Type: TABLE DATA; Schema: public; Owner: disruptiq
--

COPY public.professionnels (id, name, company_name, email, phone, category, specialties, address, city, postal_code, rating, total_jobs, last_contacted, notes, is_indexed, last_indexed_at, created_at, updated_at, siret, description, statut) FROM stdin;
1	Nadege Moussu	Moussu Nurse	nm@infirmier.com	3378245568	santé	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:16.201988+00	2025-11-01 12:13:43.617515+00	2025-11-01 13:23:15.348887+00	\N	\N	active
2	Sabrina Moussu	SM Avocat	sm@smavocats.com	3378245568	Droit de la PI	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:16.945028+00	2025-11-01 12:13:43.617515+00	2025-11-01 13:23:16.945974+00	\N	\N	active
3	Jerome Caranta	JC	JC@gmail.com		Juriste	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:17.153435+00	2025-11-01 12:13:43.617515+00	2025-11-01 13:23:17.154737+00	\N	\N	active
4	Lucas Martin	Martin Plomberie	lucas.martin@exemple.fr	33782455684	Plombier	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:17.36037+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:17.361263+00	\N	\N	active
5	Claire Dupont	Dupont Électricité	claire.dupont@exemple.fr	33782455684	Électricien	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:17.573522+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:17.575016+00	\N	\N	active
6	Antoine Moreau	Moreau Chauffage	antoine.moreau@exemple.fr	33782455684	Chauffagiste	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:19.344148+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:19.345381+00	\N	\N	active
7	Sophie Bernard	Bernard Serrurerie	sophie.bernard@exemple.fr	33782455684	Serrurier	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:19.568706+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:19.570643+00	\N	\N	active
8	Julien Petit	Petit Nettoyage	 julien.petit@exemple.fr	33782455684	Nettoyage	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:19.790058+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:19.791019+00	\N	\N	active
9	Marie Lefèvre	Lefèvre Jardins	marie.lefevre@exemple.fr	33782455684	Jardinier	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:20.061597+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:20.064246+00	\N	\N	active
10	Nicolas Garnier	Garnier Rénovation	nicolas.garnier@exemple.fr	33782455684	Peintre	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:20.283013+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:20.283769+00	\N	\N	active
11	Élise Roux	Roux Toiture	elise.roux@exemple.fr	33782455684	Toiture	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:20.477778+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:20.479217+00	\N	\N	active
12	Marc Morel	Morel Vitres	marc.morel@exemple.fr	33782455684	Vitrerie	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:20.701575+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:20.702681+00	\N	\N	active
13	Hélène Faure	Faure Ascenseurs	helene.faure@exemple.fr	33782455684	Ascensoriste	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:20.979082+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:20.97984+00	\N	\N	active
14	Damien Renaud	Renaud Dépannage	damien.renaud@exemple.fr	33782455684	Dépannage électrique	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:21.186633+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:21.187808+00	\N	\N	active
15	Aline Caron	Caron Sols	 aline.caron@exemple.fr	33782455684	Carrelage	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:21.457135+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:21.457965+00	\N	\N	active
16	Olivier Pires	Pires Chauffage	olivier.pires@exemple.fr	33782455684	Chaudières	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:21.651664+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:21.652913+00	\N	\N	active
17	Isabelle Marchand	Marchand Sécurité	isabelle.marchand@exemple.fr	33782455684	Sécurité	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:21.892015+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:21.89342+00	\N	\N	active
18	Thomas Gauthier	Gauthier Peinture	thomas.gauthier@exemple.fr	33782455684	Peintre	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:22.088979+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:22.08977+00	\N	\N	active
19	Laura Vidal	Vidal Nettoyage	laura.vidal@exemple.fr	33782455684	Nettoyage	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:22.291698+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:22.292721+00	\N	\N	active
20	Sébastien Roy	Roy Serrurerie	sebastien.roy@exemple.fr	33782455684	Serrurier	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:22.497687+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:22.499756+00	\N	\N	active
21	Amandine Bernard	Bernard Espaces Verts	amandine.bernard@exemple.fr	33782455684	Jardinier	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:22.748634+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:22.749427+00	\N	\N	active
22	Romain Bruno	Bruno Plomberie	romain.bruno@exemple.fr	33782455684	Plombier	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:23.091344+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:23.092174+00	\N	\N	active
23	Caroline Millet	Millet Climatisation	caroline.millet@exemple.fr	33782455684	Climatisation	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:23.305097+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:23.305942+00	\N	\N	active
24	David Petit	Petit Couvreur	david.petit@exemple.fr	33782455684	Couvreur	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:23.508062+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:23.509387+00	\N	\N	active
25	Julie Morel	Morel Diagnostics	julie.morel@exemple.fr	33782455684	Diagnostic immobilier	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:23.726226+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:23.727076+00	\N	\N	active
26	François Lambert	Lambert Énergies	francois.lambert@exemple.fr	33782455684	Électricien	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:23.946728+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:23.948183+00	\N	\N	active
27	Marine Simon	Simon Hygiène	marine.simon@exemple.fr	33782455684	Pulvérisation & nettoyage	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:24.149215+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:24.150112+00	\N	\N	active
28	Vincent Noel	Noel Serrurerie	vincent.noel@exemple.fr	33782455684	Serrurier	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:24.365675+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:24.367031+00	\N	\N	active
29	Anaïs Dubois	Dubois Architectes	anais.dubois@exemple.fr	33782455684	Architecte	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:24.575047+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:24.57642+00	\N	\N	active
30	Pierre Olivier	Olivier Vitrerie	pierre.olivier@exemple.fr	33782455684	Vitrerie	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:24.817838+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:24.819473+00	\N	\N	active
31	Camille Lefort	Lefort Ascenseurs	camille.lefort@exemple.fr	33782455684	Ascensoriste	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:25.076482+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:25.077378+00	\N	\N	active
32	Benoît Gerard	Gerard Chauffage	benoit.gerard@exemple.fr	33782455684	Chauffagiste	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:25.323701+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:25.32452+00	\N	\N	active
33	Laetitia Perrot	Perrot Nettoyage	laetitia.perrot@exemple.fr	33782455684	Nettoyage	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:25.541273+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:25.542688+00	\N	\N	active
34	Alexandre Colin	Colin Travaux	alex.colin@exemple.fr	33782455684	Général travaux	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:25.730783+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:25.731566+00	\N	\N	active
35	Nathalie Dupuis	Dupuis Entretien	nathalie.dupuis@exemple.fr	33782455684	Entretien parties communes	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:25.922451+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:25.923211+00	\N	\N	active
36	Mathieu Rolland	Rolland Sécurité	mathieu.rolland@exemple.fr	33782455684	Système d'alarme	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:26.157039+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:26.157797+00	\N	\N	active
37	Sabrina Marchal	Marchal Jardins	sabrina.marchal@exemple.fr	33782455684	Jardinier	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:26.40125+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:26.402035+00	\N	\N	active
38	Laurent Mercier	Mercier Plomberie	laurent.mercier@exemple.fr	33782455684	Plombier	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:26.60887+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:26.609991+00	\N	\N	active
39	Emilie Faure	Faure Peinture	emilie.faure@exemple.fr	33782455684	Peintre	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:26.820934+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:26.822211+00	\N	\N	active
40	Stéphane Lebrun	Lebrun Électricité	stephane.lebrun@exemple.fr	33782455684	Électricien	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:27.062088+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:27.062827+00	\N	\N	active
41	Claire Girard	Girard Sols	claire.girard@exemple.fr	33782455684	Parquet & sol	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:27.304096+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:27.305769+00	\N	\N	active
42	Julien Noel	Noel Fermetures	julien.noel@exemple.fr	33782455684	Menuiserie 	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:27.518504+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:27.519214+00	\N	\N	active
43	Sonia Hubert	Hubert Nettoyage	sonia.hubert@exemple.fr	33782455684	Nettoyage professionnel	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:27.74832+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:27.750034+00	\N	\N	active
44	Grégoire Fontaine	Fontaine Ascenseurs	gregoire.fontaine@exemple.fr	33782455684	Ascensoriste	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:27.977962+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:27.978739+00	\N	\N	active
45	Manon Leroux	Leroux Paysage	manon.leroux@exemple.fr	33782455684	Paysagiste	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:28.188514+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:28.189354+00	\N	\N	active
46	Eric Bernard	Bernard Toiture	eric.bernard@exemple.fr	33782455684	Toiture	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:28.516687+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:28.517742+00	\N	\N	active
47	Valérie Denis	Denis Clim	valerie.denis@exemple.fr	33782455684	Climatisation	[]	\N	\N	\N	0	0	\N	\N	t	2025-11-01 13:23:28.751855+00	2025-11-01 12:14:34.512059+00	2025-11-01 13:23:28.753234+00	\N	\N	active
\.


--
-- Data for Name: professionnels_coproprietes; Type: TABLE DATA; Schema: public; Owner: disruptiq
--

COPY public.professionnels_coproprietes (professionnel_id, copropriete_id, date_debut, date_fin, est_prestataire_principal, nombre_interventions, derniere_intervention, note_moyenne, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: disruptiq
--

COPY public.users (id, email, hashed_password, full_name, is_active, is_superuser, created_at, updated_at) FROM stdin;
\.


--
-- Name: coproprietaires_id_seq; Type: SEQUENCE SET; Schema: public; Owner: disruptiq
--

SELECT pg_catalog.setval('public.coproprietaires_id_seq', 1, true);


--
-- Name: coproprietes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: disruptiq
--

SELECT pg_catalog.setval('public.coproprietes_id_seq', 1, true);


--
-- Name: documents_id_seq; Type: SEQUENCE SET; Schema: public; Owner: disruptiq
--

SELECT pg_catalog.setval('public.documents_id_seq', 1, false);


--
-- Name: emails_id_seq; Type: SEQUENCE SET; Schema: public; Owner: disruptiq
--

SELECT pg_catalog.setval('public.emails_id_seq', 13, true);


--
-- Name: professionnels_id_seq; Type: SEQUENCE SET; Schema: public; Owner: disruptiq
--

SELECT pg_catalog.setval('public.professionnels_id_seq', 47, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: disruptiq
--

SELECT pg_catalog.setval('public.users_id_seq', 1, false);


--
-- Name: coproprietaires coproprietaires_pkey; Type: CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.coproprietaires
    ADD CONSTRAINT coproprietaires_pkey PRIMARY KEY (id);


--
-- Name: coproprietes coproprietes_pkey; Type: CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.coproprietes
    ADD CONSTRAINT coproprietes_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: emails emails_pkey; Type: CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.emails
    ADD CONSTRAINT emails_pkey PRIMARY KEY (id);


--
-- Name: professionnels_coproprietes professionnels_coproprietes_pkey; Type: CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.professionnels_coproprietes
    ADD CONSTRAINT professionnels_coproprietes_pkey PRIMARY KEY (professionnel_id, copropriete_id);


--
-- Name: coproprietaires unique_lot_per_copropriete; Type: CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.coproprietaires
    ADD CONSTRAINT unique_lot_per_copropriete UNIQUE (copropriete_id, numero_lot);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: professionnels vendors_pkey; Type: CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.professionnels
    ADD CONSTRAINT vendors_pkey PRIMARY KEY (id);


--
-- Name: idx_coproprietaires_copro_statut; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietaires_copro_statut ON public.coproprietaires USING btree (copropriete_id, statut);


--
-- Name: idx_coproprietaires_copropriete; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietaires_copropriete ON public.coproprietaires USING btree (copropriete_id);


--
-- Name: idx_coproprietaires_email; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietaires_email ON public.coproprietaires USING btree (email);


--
-- Name: idx_coproprietaires_is_indexed; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietaires_is_indexed ON public.coproprietaires USING btree (is_indexed);


--
-- Name: idx_coproprietaires_nom; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietaires_nom ON public.coproprietaires USING btree (nom);


--
-- Name: idx_coproprietaires_nom_prenom; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietaires_nom_prenom ON public.coproprietaires USING btree (nom, prenom);


--
-- Name: idx_coproprietaires_not_indexed; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietaires_not_indexed ON public.coproprietaires USING btree (is_indexed) WHERE (is_indexed = false);


--
-- Name: idx_coproprietaires_numero_lot; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietaires_numero_lot ON public.coproprietaires USING btree (numero_lot);


--
-- Name: idx_coproprietaires_prenom; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietaires_prenom ON public.coproprietaires USING btree (prenom);


--
-- Name: idx_coproprietaires_statut; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietaires_statut ON public.coproprietaires USING btree (statut);


--
-- Name: idx_coproprietes_code_postal; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietes_code_postal ON public.coproprietes USING btree (code_postal);


--
-- Name: idx_coproprietes_created; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietes_created ON public.coproprietes USING btree (created_at DESC);


--
-- Name: idx_coproprietes_is_indexed; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietes_is_indexed ON public.coproprietes USING btree (is_indexed);


--
-- Name: idx_coproprietes_not_indexed; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietes_not_indexed ON public.coproprietes USING btree (is_indexed) WHERE (is_indexed = false);


--
-- Name: idx_coproprietes_syndic; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietes_syndic ON public.coproprietes USING btree (syndic);


--
-- Name: idx_coproprietes_ville; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietes_ville ON public.coproprietes USING btree (ville);


--
-- Name: idx_coproprietes_ville_code_postal; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_coproprietes_ville_code_postal ON public.coproprietes USING btree (ville, code_postal);


--
-- Name: idx_documents_coproprietaire; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_documents_coproprietaire ON public.documents USING btree (coproprietaire_id);


--
-- Name: idx_documents_copropriete; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_documents_copropriete ON public.documents USING btree (copropriete_id);


--
-- Name: idx_documents_professionnel; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_documents_professionnel ON public.documents USING btree (professionnel_id);


--
-- Name: idx_emails_coproprietaire; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_emails_coproprietaire ON public.emails USING btree (coproprietaire_id);


--
-- Name: idx_emails_copropriete; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_emails_copropriete ON public.emails USING btree (copropriete_id);


--
-- Name: idx_emails_professionnel; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_emails_professionnel ON public.emails USING btree (professionnel_id);


--
-- Name: idx_prof_copro_actif; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_prof_copro_actif ON public.professionnels_coproprietes USING btree (date_fin) WHERE (date_fin IS NULL);


--
-- Name: idx_prof_copro_copropriete; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_prof_copro_copropriete ON public.professionnels_coproprietes USING btree (copropriete_id);


--
-- Name: idx_prof_copro_professionnel; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_prof_copro_professionnel ON public.professionnels_coproprietes USING btree (professionnel_id);


--
-- Name: idx_professionnels_category; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_professionnels_category ON public.professionnels USING btree (category);


--
-- Name: idx_professionnels_category_city; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_professionnels_category_city ON public.professionnels USING btree (category, city);


--
-- Name: idx_professionnels_city; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_professionnels_city ON public.professionnels USING btree (city);


--
-- Name: idx_professionnels_created; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_professionnels_created ON public.professionnels USING btree (created_at DESC);


--
-- Name: idx_professionnels_email; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_professionnels_email ON public.professionnels USING btree (email);


--
-- Name: idx_professionnels_is_indexed; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_professionnels_is_indexed ON public.professionnels USING btree (is_indexed);


--
-- Name: idx_professionnels_not_indexed; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_professionnels_not_indexed ON public.professionnels USING btree (is_indexed) WHERE (is_indexed = false);


--
-- Name: idx_professionnels_statut; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX idx_professionnels_statut ON public.professionnels USING btree (statut);


--
-- Name: ix_documents_document_type; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_documents_document_type ON public.documents USING btree (document_type);


--
-- Name: ix_documents_id; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_documents_id ON public.documents USING btree (id);


--
-- Name: ix_documents_property_id; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_documents_property_id ON public.documents USING btree (property_id);


--
-- Name: ix_documents_qdrant_id; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_documents_qdrant_id ON public.documents USING btree (qdrant_id);


--
-- Name: ix_documents_vendor_id; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_documents_vendor_id ON public.documents USING btree (vendor_id);


--
-- Name: ix_emails_id; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_emails_id ON public.emails USING btree (id);


--
-- Name: ix_emails_message_id; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE UNIQUE INDEX ix_emails_message_id ON public.emails USING btree (message_id);


--
-- Name: ix_emails_thread_id; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_emails_thread_id ON public.emails USING btree (thread_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_vendors_category; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_vendors_category ON public.professionnels USING btree (category);


--
-- Name: ix_vendors_email; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE UNIQUE INDEX ix_vendors_email ON public.professionnels USING btree (email);


--
-- Name: ix_vendors_id; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_vendors_id ON public.professionnels USING btree (id);


--
-- Name: ix_vendors_is_indexed; Type: INDEX; Schema: public; Owner: disruptiq
--

CREATE INDEX ix_vendors_is_indexed ON public.professionnels USING btree (is_indexed);


--
-- Name: coproprietaires fk_copropriete; Type: FK CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.coproprietaires
    ADD CONSTRAINT fk_copropriete FOREIGN KEY (copropriete_id) REFERENCES public.coproprietes(id) ON DELETE CASCADE;


--
-- Name: professionnels_coproprietes fk_copropriete_liaison; Type: FK CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.professionnels_coproprietes
    ADD CONSTRAINT fk_copropriete_liaison FOREIGN KEY (copropriete_id) REFERENCES public.coproprietes(id) ON DELETE CASCADE;


--
-- Name: documents fk_documents_coproprietaire; Type: FK CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_documents_coproprietaire FOREIGN KEY (coproprietaire_id) REFERENCES public.coproprietaires(id) ON DELETE SET NULL;


--
-- Name: documents fk_documents_copropriete; Type: FK CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_documents_copropriete FOREIGN KEY (copropriete_id) REFERENCES public.coproprietes(id) ON DELETE SET NULL;


--
-- Name: documents fk_documents_professionnel; Type: FK CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_documents_professionnel FOREIGN KEY (professionnel_id) REFERENCES public.professionnels(id) ON DELETE SET NULL;


--
-- Name: emails fk_emails_coproprietaire; Type: FK CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.emails
    ADD CONSTRAINT fk_emails_coproprietaire FOREIGN KEY (coproprietaire_id) REFERENCES public.coproprietaires(id) ON DELETE SET NULL;


--
-- Name: emails fk_emails_copropriete; Type: FK CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.emails
    ADD CONSTRAINT fk_emails_copropriete FOREIGN KEY (copropriete_id) REFERENCES public.coproprietes(id) ON DELETE SET NULL;


--
-- Name: emails fk_emails_professionnel; Type: FK CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.emails
    ADD CONSTRAINT fk_emails_professionnel FOREIGN KEY (professionnel_id) REFERENCES public.professionnels(id) ON DELETE SET NULL;


--
-- Name: professionnels_coproprietes fk_professionnel; Type: FK CONSTRAINT; Schema: public; Owner: disruptiq
--

ALTER TABLE ONLY public.professionnels_coproprietes
    ADD CONSTRAINT fk_professionnel FOREIGN KEY (professionnel_id) REFERENCES public.professionnels(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict fvahrPMApMRkebMy3fuoxB7yx3ymFB64OvsMFwnT3ZA66RgbBXBuLVKmZzRgt9p

