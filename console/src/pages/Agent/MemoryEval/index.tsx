import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type React from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Row,
  Select,
  Table,
  Tabs,
  Tag,
  Upload,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  Activity,
  BarChart3,
  BrainCircuit,
  Clock3,
  FileJson,
  FileUp,
  Gauge,
  Play,
  RotateCcw,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import api from "../../../api";
import type {
  MemoryCompactionCaseMetric,
  MemoryEvalReport,
  MemorySearchCaseMetric,
} from "../../../api/types/eval";
import styles from "./index.module.less";

const percentMetrics = [
  "search_avg_recall_at_k",
  "search_avg_mrr",
  "search_avg_ndcg",
  "search_avg_exclusion_rate",
  "compaction_avg_retention_rate",
  "compaction_avg_safety_rate",
  "compaction_avg_compression_ratio",
  "architecture_score",
  "architecture_index_exists",
  "architecture_index_under_limit",
];

function formatNumber(value?: number, digits = 2) {
  if (value === undefined || Number.isNaN(value)) return "-";
  return value.toFixed(digits);
}

function formatPercent(value?: number) {
  if (value === undefined || Number.isNaN(value)) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

function MetricCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: "blue" | "green" | "orange" | "red";
}) {
  return (
    <Card className={styles.metricCard}>
      <div className={`${styles.metricIcon} ${styles[tone]}`}>{icon}</div>
      <div className={styles.metricText}>
        <span className={styles.metricLabel}>{label}</span>
        <strong className={styles.metricValue}>{value}</strong>
      </div>
    </Card>
  );
}

function BarMetric({
  label,
  value,
}: {
  label: string;
  value: number | undefined;
}) {
  const safeValue = Math.max(0, Math.min(1, value ?? 0));
  return (
    <div className={styles.barMetric}>
      <div className={styles.barMetricHeader}>
        <span>{label}</span>
        <strong>{formatPercent(value)}</strong>
      </div>
      <div className={styles.barTrack}>
        <div
          className={styles.barFill}
          style={{ width: `${safeValue * 100}%` }}
        />
      </div>
    </div>
  );
}

function MemoryEvalPage() {
  const { t } = useTranslation();
  const [backend, setBackend] = useState<"keyword" | "copaw">("keyword");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<MemoryEvalReport | null>(null);
  const [customSuite, setCustomSuite] = useState<Record<string, unknown> | null>(null);
  const [suiteName, setSuiteName] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSuiteUpload = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const parsed = JSON.parse(e.target?.result as string);
        setCustomSuite(parsed);
        setSuiteName(file.name);
        message.success(t("memoryEval.suiteLoaded", "Suite loaded: {{name}}", { name: file.name }));
      } catch {
        message.error(t("memoryEval.suiteParseError", "Invalid JSON file"));
      }
    };
    reader.readAsText(file);
    return false;
  }, [t]);

  const clearSuite = useCallback(() => {
    setCustomSuite(null);
    setSuiteName("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  const runEval = useCallback(async (selectedBackend: "keyword" | "copaw") => {
    setLoading(true);
    try {
      const data = await api.runMemoryEval({
        backend: selectedBackend,
        suite: customSuite ?? undefined,
      });
      setReport(data);
      message.success(t("memoryEval.runSuccess", "Memory evaluation finished"));
    } catch (err) {
      const errMsg =
        err instanceof Error
          ? err.message
          : t("memoryEval.runFailed", "Failed to run memory evaluation");
      message.error(errMsg);
    } finally {
      setLoading(false);
    }
  }, [t, customSuite]);

  useEffect(() => {
    runEval("keyword");
  }, []);

  const summary = report?.summary ?? {};

  const searchColumns: ColumnsType<MemorySearchCaseMetric> = useMemo(
    () => [
      {
        title: t("memoryEval.caseId", "Case"),
        dataIndex: "case_id",
        key: "case_id",
        width: 220,
      },
      {
        title: t("memoryEval.returned", "Returned"),
        dataIndex: "returned_ids",
        key: "returned_ids",
        render: (ids: string[]) => (
          <div className={styles.tagList}>
            {ids.map((id) => (
              <Tag key={id}>{id}</Tag>
            ))}
          </div>
        ),
      },
      {
        title: t("memoryEval.forbidden", "禁止项"),
        dataIndex: "forbidden_returned_ids",
        key: "forbidden_returned_ids",
        width: 160,
        render: (ids?: string[]) =>
          ids && ids.length > 0 ? (
            <div className={styles.tagList}>
              {ids.map((id) => (
                <Tag key={id} color="red">
                  {id}
                </Tag>
              ))}
            </div>
          ) : (
            <Tag color="green">{t("memoryEval.clean", "干净")}</Tag>
          ),
      },
      {
        title: "Recall@K",
        dataIndex: "recall_at_k",
        key: "recall_at_k",
        width: 120,
        render: formatPercent,
      },
      {
        title: "MRR",
        dataIndex: "mrr",
        key: "mrr",
        width: 100,
        render: (value: number) => formatNumber(value, 3),
      },
      {
        title: "nDCG",
        dataIndex: "ndcg",
        key: "ndcg",
        width: 100,
        render: (value: number) => formatNumber(value, 3),
      },
      {
        title: t("memoryEval.exclusion", "排除率"),
        dataIndex: "exclusion_rate",
        key: "exclusion_rate",
        width: 120,
        render: formatPercent,
      },
      {
        title: t("memoryEval.latency", "Latency"),
        dataIndex: "latency_ms",
        key: "latency_ms",
        width: 120,
        render: (value: number) => `${formatNumber(value, 1)} ms`,
      },
      {
        title: t("memoryEval.status", "Status"),
        dataIndex: "error",
        key: "error",
        width: 110,
        render: (error?: string | null) =>
          error ? <Tag color="red">{t("memoryEval.error", "Error")}</Tag> : <Tag color="green">{t("memoryEval.ok", "OK")}</Tag>,
      },
    ],
    [t],
  );

  const compactionColumns: ColumnsType<MemoryCompactionCaseMetric> = useMemo(
    () => [
      {
        title: t("memoryEval.caseId", "Case"),
        dataIndex: "case_id",
        key: "case_id",
      },
      {
        title: t("memoryEval.sourceTokens", "Source"),
        dataIndex: "source_tokens",
        key: "source_tokens",
        width: 110,
      },
      {
        title: t("memoryEval.summaryTokens", "Summary"),
        dataIndex: "summary_tokens",
        key: "summary_tokens",
        width: 120,
      },
      {
        title: t("memoryEval.compression", "Compression"),
        dataIndex: "compression_ratio",
        key: "compression_ratio",
        width: 130,
        render: formatPercent,
      },
      {
        title: t("memoryEval.retention", "Retention"),
        dataIndex: "retention_rate",
        key: "retention_rate",
        width: 120,
        render: formatPercent,
      },
      {
        title: t("memoryEval.safety", "安全率"),
        dataIndex: "safety_rate",
        key: "safety_rate",
        width: 110,
        render: formatPercent,
      },
      {
        title: t("memoryEval.forbidden", "禁止项"),
        dataIndex: "forbidden_terms_found",
        key: "forbidden_terms_found",
        width: 180,
        render: (terms?: string[]) =>
          terms && terms.length > 0 ? (
            <div className={styles.tagList}>
              {terms.map((term) => (
                <Tag key={term} color="red">
                  {term}
                </Tag>
              ))}
            </div>
          ) : (
            <Tag color="green">{t("memoryEval.clean", "干净")}</Tag>
          ),
      },
      {
        title: t("memoryEval.latency", "Latency"),
        dataIndex: "latency_ms",
        key: "latency_ms",
        width: 120,
        render: (value: number) => `${formatNumber(value, 1)} ms`,
      },
      {
        title: t("memoryEval.status", "Status"),
        dataIndex: "over_budget",
        key: "over_budget",
        width: 120,
        render: (overBudget: boolean, row: MemoryCompactionCaseMetric) =>
          row.error ? (
            <Tag color="red">{t("memoryEval.error", "Error")}</Tag>
          ) : row.forbidden_terms_found?.length ? (
            <Tag color="red">{t("memoryEval.leak", "泄露")}</Tag>
          ) : overBudget ? (
            <Tag color="orange">{t("memoryEval.budget", "Budget")}</Tag>
          ) : (
            <Tag color="green">{t("memoryEval.ok", "OK")}</Tag>
          ),
      },
    ],
    [t],
  );

  const jsonReport = report
    ? JSON.stringify(report, null, 2)
    : t("memoryEval.noReport", "No report yet");

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>
            {t("memoryEval.title", "Memory Evaluation")}
          </h1>
          <p className={styles.description}>
            {t(
              "memoryEval.description",
              "Run retrieval and compaction benchmarks against CoPaw memory.",
            )}
          </p>
        </div>
        <div className={styles.actions}>
          <Select
            value={backend}
            onChange={setBackend}
            className={styles.backendSelect}
            options={[
              { value: "keyword", label: t("memoryEval.keywordBaseline", "Keyword baseline") },
              { value: "copaw", label: t("memoryEval.copawBackend", "CoPaw MemoryManager") },
            ]}
          />
          <Upload
            accept=".json"
            showUploadList={false}
            beforeUpload={handleSuiteUpload}
          >
            <Button icon={<FileUp size={16} />}>
              {t("memoryEval.loadSuite", "Load Suite")}
            </Button>
          </Upload>
          <Button
            icon={<RotateCcw size={16} />}
            onClick={() => setReport(null)}
          >
            {t("memoryEval.clear", "Clear")}
          </Button>
          <Button
            type="primary"
            icon={<Play size={16} />}
            loading={loading}
            onClick={() => runEval(backend)}
          >
            {t("memoryEval.run", "Run")}
          </Button>
        </div>
      </div>

      {customSuite && (
        <Alert
          className={styles.alert}
          type="success"
          showIcon
          message={
            <div className={styles.suiteAlertContent}>
              <span>{t("memoryEval.suiteLoaded", "Suite loaded: {{name}}", { name: suiteName })}</span>
              <Button
                type="text"
                size="small"
                icon={<X size={14} />}
                onClick={clearSuite}
              />
            </div>
          }
        />
      )}

      {backend === "copaw" && (
        <Alert
          className={styles.alert}
          type="info"
          showIcon
          message={t(
            "memoryEval.copawHint",
            "The CoPaw backend uses the real MemoryManager and requires memory dependencies and embedding configuration.",
          )}
        />
      )}

      <Row gutter={[16, 16]} className={styles.metricsGrid}>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            tone="blue"
            icon={<BrainCircuit size={20} />}
            label="Recall@K"
            value={formatPercent(summary.search_avg_recall_at_k)}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            tone="green"
            icon={<BarChart3 size={20} />}
            label="MRR"
            value={formatNumber(summary.search_avg_mrr, 3)}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            tone="orange"
            icon={<Gauge size={20} />}
            label={t("memoryEval.retention", "Retention")}
            value={formatPercent(summary.compaction_avg_retention_rate)}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            tone="red"
            icon={<Clock3 size={20} />}
            label={t("memoryEval.latency", "Latency")}
            value={`${formatNumber(summary.search_avg_latency_ms, 1)} ms`}
          />
        </Col>
      </Row>

      <div className={styles.panels}>
        <Card className={styles.chartPanel}>
          <div className={styles.panelTitle}>
            <Activity size={18} />
            <span>{t("memoryEval.metricProfile", "Metric Profile")}</span>
          </div>
          <div className={styles.barList}>
            {percentMetrics.map((metric) => (
              <BarMetric
                key={metric}
                label={metric.replace(/_/g, " ")}
                value={summary[metric]}
              />
            ))}
          </div>
        </Card>

        <Card className={styles.infoPanel}>
          <div className={styles.panelTitle}>
            <FileJson size={18} />
            <span>{t("memoryEval.runInfo", "Run Info")}</span>
          </div>
          <dl className={styles.infoList}>
            <dt>{t("memoryEval.suite", "Suite")}</dt>
            <dd>{report?.suite_name ?? "-"}</dd>
            <dt>{t("memoryEval.backend", "Backend")}</dt>
            <dd>{report?.backend_name ?? backend}</dd>
            <dt>{t("memoryEval.searchCases", "Search Cases")}</dt>
            <dd>{report?.search_cases.length ?? 0}</dd>
            <dt>{t("memoryEval.compactionCases", "Compaction Cases")}</dt>
            <dd>{report?.compaction_cases.length ?? 0}</dd>
            <dt>{t("memoryEval.topicFiles", "Topic Files")}</dt>
            <dd>{report?.architecture?.topic_file_count ?? 0}</dd>
            <dt>{t("memoryEval.architectureIssues", "Architecture Issues")}</dt>
            <dd>{report?.architecture?.issue_count ?? 0}</dd>
            <dt>{t("memoryEval.indexLines", "Index Lines")}</dt>
            <dd>{report?.architecture?.index_line_count ?? 0}</dd>
          </dl>
        </Card>
      </div>

      <Tabs
        className={styles.tabs}
        items={[
          {
            key: "search",
            label: t("memoryEval.search", "Search"),
            children: (
              <Table
                rowKey="case_id"
                columns={searchColumns}
                dataSource={report?.search_cases ?? []}
                loading={loading}
                pagination={false}
                scroll={{ x: 1080 }}
              />
            ),
          },
          {
            key: "compaction",
            label: t("memoryEval.compaction", "Compaction"),
            children: (
              <Table
                rowKey="case_id"
                columns={compactionColumns}
                dataSource={report?.compaction_cases ?? []}
                loading={loading}
                pagination={false}
                scroll={{ x: 1120 }}
              />
            ),
          },
          {
            key: "json",
            label: "JSON",
            children: <pre className={styles.jsonBlock}>{jsonReport}</pre>,
          },
        ]}
      />
    </div>
  );
}

export default MemoryEvalPage;
