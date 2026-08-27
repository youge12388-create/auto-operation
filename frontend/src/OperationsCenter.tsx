import { useMemo, useState } from "react";

import type { Job, JobEvent, Strategy } from "./api";
import { Icon, StatusPill } from "./design";
import {
  FIXED_JOB_STAGES,
  formatJobDate,
  formatJobDuration,
  getJobEventLabel,
  getJobEventStatusLabel,
  getJobEventTone,
  getJobStageLabel,
  getJobStatusMeta,
  getOperatorSafeJobError,
  isActiveJob,
  isCancelableJob,
  isFailureJob,
  isRetryableJob,
} from "./jobPresentation";

type JobFilter = "all" | "active" | "attention" | "waiting" | "completed";

type Props = {
  jobs: Job[];
  strategies: Strategy[];
  selectedJobId: string | null;
  events: JobEvent[];
  eventsLoading?: boolean;
  eventsError?: string;
  retrying?: boolean;
  canceling?: boolean;
  onSelectJob: (jobId: string) => void;
  onRefresh: () => void;
  onRetry: (jobId: string) => void;
  onCancel: (jobId: string) => void;
};

function jobTitle(job: Job, strategies: Strategy[]) {
  const strategy = strategies.find((item) => item.id === job.strategy_id);
  return strategy?.name || `自动化任务 ${job.id.slice(0, 8)}`;
}

function statusClass(job: Job) {
  if (isFailureJob(job)) return "is-attention";
  if (job.status === "succeeded") return "is-complete";
  if (isActiveJob(job)) return "is-running";
  return "";
}

function statusIcon(job: Job) {
  if (isFailureJob(job)) return "alert" as const;
  if (job.status === "succeeded") return "check" as const;
  if (isActiveJob(job)) return "refresh" as const;
  return "clock" as const;
}

function eventIcon(tone: ReturnType<typeof getJobEventTone>) {
  if (tone === "red") return "alert" as const;
  if (tone === "green") return "check" as const;
  if (tone === "blue") return "refresh" as const;
  return "clock" as const;
}

function eventClass(tone: ReturnType<typeof getJobEventTone>) {
  if (tone === "red") return "is-attention";
  if (tone === "green") return "is-complete";
  return "";
}

function jobProgress(job: Job) {
  if (job.status === "succeeded") return 100;
  const stageIndex = job.current_step ? FIXED_JOB_STAGES.indexOf(job.current_step as (typeof FIXED_JOB_STAGES)[number]) : -1;
  if (stageIndex < 0) return isActiveJob(job) ? 5 : 0;
  const completion = job.status === "running" ? stageIndex + 0.45 : stageIndex;
  return Math.max(5, Math.min(96, Math.round((completion / FIXED_JOB_STAGES.length) * 100)));
}

function matchesFilter(job: Job, filter: JobFilter) {
  if (filter === "all") return true;
  if (filter === "active") return isActiveJob(job);
  if (filter === "attention") return isFailureJob(job);
  if (filter === "waiting") return ["waiting_topic", "waiting_review"].includes(job.status);
  return job.status === "succeeded";
}

function copyErrorText(value: string) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(value);
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  return copied ? Promise.resolve() : Promise.reject(new Error("浏览器不支持复制"));
}

export function OperationsCenter({
  jobs,
  strategies,
  selectedJobId,
  events,
  eventsLoading = false,
  eventsError = "",
  retrying = false,
  canceling = false,
  onSelectJob,
  onRefresh,
  onRetry,
  onCancel,
}: Props) {
  const [filter, setFilter] = useState<JobFilter>("all");
  const [copyNotice, setCopyNotice] = useState("");
  const selectedJob = jobs.find((item) => item.id === selectedJobId) ?? null;
  const filteredJobs = useMemo(() => jobs.filter((job) => matchesFilter(job, filter)), [filter, jobs]);
  const activeCount = jobs.filter(isActiveJob).length;
  const attentionCount = jobs.filter(isFailureJob).length;
  const waitingCount = jobs.filter((job) => ["waiting_topic", "waiting_review"].includes(job.status)).length;
  const completeCount = jobs.filter((job) => job.status === "succeeded").length;
  const safeError = selectedJob && isFailureJob(selectedJob) ? getOperatorSafeJobError(selectedJob, events) : null;
  const selectedStatus = selectedJob ? getJobStatusMeta(selectedJob.status) : null;
  const progress = selectedJob ? jobProgress(selectedJob) : 0;

  const summaries: Array<{ key: JobFilter; label: string; count: number; note: string; className: string }> = [
    { key: "active", label: "正在运行", count: activeCount, note: "排队或正在执行的任务", className: "summary-running" },
    { key: "attention", label: "需要处理", count: attentionCount, note: "失败任务可查看原因并重试", className: "summary-attention" },
    { key: "waiting", label: "等待人工", count: waitingCount, note: "等待选题或审核确认", className: "" },
    { key: "completed", label: "已完成", count: completeCount, note: "本次列表中的成功任务", className: "summary-complete" },
  ];

  return <main className="figma-page operations-page">
    <div className="figma-page-heading operations-heading">
      <div>
        <h1><Icon name="chart" size={25} />运行中心</h1>
        <p>查看自动化任务的实时状态、执行阶段和可处理的错误。不会展示模型密钥或运行配置。</p>
      </div>
      <div className="operations-heading-actions">
        <span className="operations-refresh-note">任务列表自动刷新</span>
        <button className="operations-plain-button" type="button" onClick={onRefresh}><Icon name="refresh" size={15} />立即刷新</button>
      </div>
    </div>

    <section className="operations-summary" aria-label="任务概览">
      {summaries.map((summary) => <button
        type="button"
        key={summary.key}
        className={`${summary.className} ${filter === summary.key ? "is-active" : ""}`}
        onClick={() => setFilter(filter === summary.key ? "all" : summary.key)}
      >
        <span>{summary.label}</span><strong>{summary.count}</strong><small>{summary.note}</small>
      </button>)}
    </section>

    <section className="operations-workspace">
      <aside className="operations-list-panel" aria-label="任务列表">
        <div className="operations-list-head">
          <div><h2>最近任务</h2><p>选择一条任务查看完整阶段和错误原因</p></div>
          <select className="operations-filter" value={filter} onChange={(event) => setFilter(event.target.value as JobFilter)} aria-label="任务筛选">
            <option value="all">全部 {jobs.length}</option>
            <option value="active">运行中 {activeCount}</option>
            <option value="attention">需处理 {attentionCount}</option>
            <option value="waiting">等待人工 {waitingCount}</option>
            <option value="completed">已完成 {completeCount}</option>
          </select>
        </div>
        <div className="operations-job-list">
          {filteredJobs.length ? filteredJobs.map((job) => {
            const meta = getJobStatusMeta(job.status);
            return <button
              type="button"
              key={job.id}
              className={`operations-job-row ${job.id === selectedJobId ? "is-selected" : ""}`}
              onClick={() => onSelectJob(job.id)}
            >
              <span className={`operations-job-status ${statusClass(job)}`}><Icon name={statusIcon(job)} size={15} /></span>
              <span className="operations-job-copy">
                <span className="operations-job-title-line"><strong>{jobTitle(job, strategies)}</strong><StatusPill tone={meta.tone}>{meta.label}</StatusPill></span>
                <small>{getJobStageLabel(job.current_step)} · 第 {job.attempt_count + 1}/{job.max_attempts} 次</small>
                <time>{formatJobDate(job.updated_at || job.created_at)}</time>
              </span>
            </button>;
          }) : <div className="operations-events-empty">当前筛选条件下没有任务。切换筛选条件，或等待下一次自动化执行。</div>}
        </div>
      </aside>

      <section className="operations-detail" aria-live="polite">
        {!selectedJob ? <div className="operations-detail-empty"><div><Icon name="chart" size={25} /><strong>选择一条任务</strong><p>这里会展示所处阶段、事件时间线和可安全查看的错误说明。</p></div></div> : <>
          <div className="operations-detail-top">
            <div className="operations-detail-title">
              <div><h2 title={jobTitle(selectedJob, strategies)}>{jobTitle(selectedJob, strategies)}</h2><StatusPill tone={selectedStatus!.tone}>{selectedStatus!.label}</StatusPill></div>
              <p>当前阶段：{getJobStageLabel(selectedJob.current_step)} · 任务 ID：{selectedJob.id.slice(0, 8)}</p>
            </div>
            <div className="operations-detail-actions">
              {isRetryableJob(selectedJob) && <button className="operations-plain-button" type="button" disabled={retrying} onClick={() => onRetry(selectedJob.id)}><Icon name="refresh" size={14} />{retrying ? "重试中" : "重新执行"}</button>}
              {isCancelableJob(selectedJob) && <button className="operations-plain-button operations-plain-button--danger" type="button" disabled={canceling} onClick={() => onCancel(selectedJob.id)}><Icon name="close" size={14} />{canceling ? "取消中" : "取消任务"}</button>}
            </div>
          </div>

          <div className="operations-metrics">
            <div><span>开始时间</span><strong>{formatJobDate(selectedJob.started_at || selectedJob.created_at)}</strong></div>
            <div><span>最近更新</span><strong>{formatJobDate(selectedJob.updated_at)}</strong></div>
            <div><span>已用时</span><strong>{formatJobDuration(selectedJob.duration_ms)}</strong></div>
            <div><span>尝试次数</span><strong>{selectedJob.attempt_count + 1} / {selectedJob.max_attempts}</strong></div>
          </div>

          <div className="operations-progress" aria-label={`执行进度 ${progress}%`}>
            <div className="operations-progress-track"><i style={{ width: `${progress}%` }} /></div><span>{progress}%</span>
          </div>

          {safeError && <div className="operations-error" role="alert">
            <div className="operations-error-head"><span><Icon name="alert" size={15} />需要处理的错误</span><button className="operations-copy-button" type="button" onClick={() => { void copyErrorText(safeError).then(() => setCopyNotice("错误说明已复制")).catch(() => setCopyNotice("当前浏览器无法复制，请手动选择文本")); }}><Icon name="copy" size={13} />复制说明</button></div>
            <p>{safeError}</p>{copyNotice && <p className="operations-copy-notice">{copyNotice}</p>}
          </div>}

          <div className="operations-timeline-head"><h3>执行事件</h3><span>{eventsLoading ? "正在同步事件…" : `${events.length} 条记录`}</span></div>
          {eventsError ? <div className="operations-events-empty">暂时无法读取事件记录：{eventsError}</div> : events.length ? <ol className="operations-timeline">{events.slice().reverse().map((event) => {
            const tone = getJobEventTone(event);
            return <li key={event.id}>
              <span className={`operations-timeline-dot ${eventClass(tone)}`}><Icon name={eventIcon(tone)} size={11} /></span>
              <span className="operations-timeline-copy"><strong>{getJobEventLabel(event)}{event.step_name ? ` · ${getJobStageLabel(event.step_name)}` : ""}</strong><p>{getJobEventStatusLabel(event.status)}</p></span>
              <time>{formatJobDate(event.created_at)}</time>
            </li>;
          })}</ol> : <div className="operations-events-empty">还没有可展示的任务事件。任务启动后会在这里按时间顺序记录。</div>}
        </>}
      </section>
    </section>
  </main>;
}
