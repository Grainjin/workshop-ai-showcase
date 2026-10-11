import type { CaseStudyContent } from './types';
import { createReleaseLinks } from './release-links';
import localArchitecture from '../../../assets/diagrams/local-full-stack.svg?url&no-inline';
import publicArchitecture from '../../../assets/diagrams/public-demo-stack.svg?url&no-inline';
import confirmationFlow from '../../../assets/diagrams/ai-confirmation-flow.svg?url&no-inline';
import providerSearchResults from '../../../assets/product/provider-search-results.png?url&no-inline';
import providerSearchFilters from '../../../assets/product/provider-search-filters-expanded.png?url&no-inline';

const releaseLinks = createReleaseLinks(import.meta.env);
const demoAction = releaseLinks[0];
const videoAction = releaseLinks[1];
const heroStatus = demoAction.target.kind === 'available'
  ? videoAction.target.kind === 'available'
    ? '个人维护的求职展示版本；已完成基线修复与演示模式验证，在线体验与产品录屏入口已配置。'
    : '个人维护的求职展示版本；已完成基线修复与演示模式验证，在线体验入口已配置，产品录屏仍在准备中。'
  : videoAction.target.kind === 'available'
    ? '个人维护的求职展示版本；已完成基线修复与演示模式验证，产品录屏入口已配置，公开部署仍在准备中。'
    : '个人维护的求职展示版本；已完成基线修复与演示模式验证，公开部署和产品录屏仍在准备中。';
const walkthroughVideoStatus = videoAction.target.kind === 'available'
  ? {
      title: '产品录屏入口已配置',
      body: '可通过下方入口观看产品录屏，并结合固定脚本与模拟支付边界核对流程。',
      linkLabel: '观看已配置产品录屏',
    }
  : {
      title: '60–90 秒录屏准备中',
      body: '页面暂不提供播放器、海报或字幕文件。待发现与位置级联路径通过新一轮浏览器验收后，再录制 H.264 视频并补充中文字幕；模拟支付必须明确说明不产生真实扣款。',
      linkLabel: null,
    };
const releaseMessages = {
  demo: {
    available: '在线体验入口已配置，可通过首屏访问；实际服务可用性与交易边界请以演示产品内说明为准。',
    'coming-soon': '轻量演示模式已通过本地验证；公开部署、角色登录与浏览器路径仍需上线验收。',
  },
  video: {
    available: '产品录屏入口已配置，可通过首屏观看；流程顺序和模拟支付边界可结合本页说明核对。',
    'coming-soon': '带字幕的产品录屏仍在准备。上方八步交易流程说明了从发现到评价的主要操作和模拟支付边界。',
  },
  github: {
    available: '公开源码入口已配置，可通过首屏查看运行说明与工程记录；本地验证范围见验证章节。',
    'coming-soon': '公开源码链接尚未配置。验证章节已列出本地工程记录的位置与范围，架构章节说明完整本地模式所需依赖。',
  },
} as const;

export const caseStudy = {
  language: 'zh-CN',
  hero: {
    id: 'overview',
    eyebrow: '产品案例 · 个人求职展示版',
    title: 'Workshop AI｜AI 本地服务交易平台',
    subtitle: '从服务发现、智能决策到预约履约的一体化 Marketplace 产品',
    status: heroStatus,
    body: ['把服务商搜索、报价比较、预约和履约连接成可追踪的交易流程。AI 帮助理解需求与评价，涉及交易变更时交由用户确认。'],
    links: releaseLinks,
  },
  problem: {
    id: 'problem', title: '选择一项本地服务，需要解决的不只是搜索',
    body: ['找到候选服务商后，用户仍需判断服务区域、资质、评价和价格，再把意向转成可执行的预约。产品围绕这条决策链组织信息与操作。'],
    tensions: [
      { title: '发现成本', body: '按服务类别与位置缩小范围，让结果与真实服务区域对应。' },
      { title: '信任判断', body: '并列呈现服务商信息和评价，AI 总结帮助阅读，原始信息保留供核对。' },
      { title: '交易连续性', body: '从收藏到报价、支付与履约保留明确状态，减少跨页面操作时的理解断点。' },
    ],
  },
  journey: {
    id: 'journey', title: '从发现到评价，把服务意向变成交易闭环',
    body: ['以 Customer 的选择过程为起点，衔接 Provider 的报价与服务交付。每一步都对应可解释的订单状态，让用户知道当前进度与下一步。'],
    steps: [
      { title: '发现', body: '选择位置与服务类别，搜索符合条件的服务商。' },
      { title: '比较', body: '查看服务范围、资质、评价与服务信息，形成候选名单。' },
      { title: '收藏', body: '保存候选服务商，为后续比较与预约保留入口。' },
      { title: '预约', body: '描述需求并选择服务，建立可追踪的预约记录。' },
      { title: '报价', body: '服务商回应需求；客户结合历史报价参考理解报价范围。' },
      { title: '支付', body: '展示版通过模拟支付推进交易状态，不产生真实扣款。' },
      { title: '履约', body: '服务完成后等待客户确认，异常情况进入退款或投诉流程。' },
      { title: '评价', body: '交易完成后留下评价，为后续服务选择提供上下文。' },
    ],
  },
  walkthrough: {
    id: 'walkthrough', title: '产品实录：保留可核对证据，不补拍不存在的流程',
    body: ['当前可核对材料包括两张已入库的真实产品搜索截图，以及固定录屏脚本和本次复现记录。旧截图与当前复现结果分开标注，避免把历史证据描述成最新端到端验收。'],
    verification: {
      title: '2026-10-12 复现状态',
      body: '新的隔离 PostgreSQL 演示数据库完成迁移与受保护重置，健康检查和一键 Customer 登录成功；进入发现流程后，Istanbul 上下文未返回预期推荐或服务商，位置级联同时显示加载错误。脚本与当前界面不一致，因此按捕获规则停止，未继续制作新的截图或视频。',
    },
    videoStatus: walkthroughVideoStatus,
    videoAction,
    demoAction,
    demoFallbackLabel: demoAction.target.kind === 'available' ? '打开 Live Demo' : '查看 Live Demo 准备状态',
    steps: [
      { title: '登录与发现', body: '使用一键 Customer 登录，确认 Public Demo 横幅、虚构数据边界和初始服务区域。' },
      { title: '筛选与收藏', body: '选择位置、类别与筛选条件，核对结果后收藏候选服务商。' },
      { title: '预约与参考价', body: '创建预约、选择服务类别，并展示基于历史样本的规则参考范围与限制。' },
      { title: 'AI 确认卡', body: '展示推荐或操作草稿；改变交易状态前停在确认卡，未经用户确认不执行。' },
      { title: '模拟支付说明', body: '展示 Demo Payment Adapter 的状态反馈，并明确说明不产生真实扣款。' },
    ],
    captures: [
      {
        src: providerSearchResults,
        alt: '服务商搜索结果页的历史验证截图',
        title: '搜索结果与候选服务商',
        description: '真实产品界面展示 Istanbul · plumbing 的搜索结果、候选服务商卡片与结果信息。',
        date: '2026-10-10',
        sourcePath: 'showcase/assets/product/provider-search-results.png',
        limitation: '历史验证截图；不是当前浏览器端到端验收，也不证明公开部署可用。',
      },
      {
        src: providerSearchFilters,
        alt: '服务商筛选面板展开状态的历史验证截图',
        title: '筛选条件与排序',
        description: '真实产品界面展示类别、距离、评分、价格、营业状态和排序条件。',
        date: '2026-10-10',
        sourcePath: 'showcase/assets/product/provider-search-filters-expanded.png',
        limitation: '历史验证截图；不是当前浏览器端到端验收，也不证明筛选后的数据已重新验收。',
      },
    ],
  },
  aiLayer: {
    id: 'ai', title: 'AI 参与理解与建议，用户保留交易决定权',
    body: ['AI 助手通过 Tool Calling 连接搜索、预约状态和操作草稿。读取与建议可以直接展示，改变业务状态的操作先生成确认卡，再由用户确认执行。'],
    capabilities: [
      { title: '需求与推荐', body: '根据用户描述整理需求，调用业务工具检索并呈现服务商推荐卡。' },
      { title: 'AI 评价总结', body: '轻量公开模式使用 PostgreSQL 数据库评价上下文进行总结，保留原始评价供核对。完整本地模式的检索无结果或不可用时回退到数据库评价上下文；未选中工具时可用规则回退整理上下文。信息不足时说明限制。' },
      { title: '确认卡', body: '预约、取消、支付与退款等操作先呈现待执行内容，确认后才推进状态。' },
      { title: '可理解的降级', body: '额度耗尽、超时或模型不可用时解释原因，普通搜索与交易流程继续可用。' },
    ],
    diagram: {
      src: confirmationFlow, title: 'AI 操作确认流程图',
      description: '从理解需求、调用工具到生成确认卡，经过用户确认后执行并返回状态；读取与建议可直接展示，交易变更保留确认步骤。',
      textLabel: 'AI 操作确认流程文字说明',
    },
    confirmationSteps: [
      { title: '理解需求', body: '结合用户描述与当前预约上下文，整理服务需求与可执行操作。' },
      { title: 'Tool Calling', body: '调用搜索、评价和状态工具；读取结果可直接展示，需要变更时先准备操作草稿。' },
      { title: '生成确认卡', body: '呈现预约、取消、支付或退款的待执行内容，确认前不改变业务状态。' },
      { title: '用户确认', body: '用户核对后选择确认；未确认时不执行，拒绝或返回后可继续普通流程。' },
      { title: '执行与反馈', body: '确认后执行相应业务操作并返回结果；失败或待核对状态应明确展示，不以模型回答代替交易结果。' },
    ],
  },
  decisionSupport: {
    id: 'decisions', title: '把比较依据放到用户做决定的地方',
    body: ['搜索筛选、位置级联和收藏减少重复查找；历史报价范围提供可解释的比较依据。价格参考来自规则统计，展示数据范围与不足，不能替代实际报价。'],
    mechanisms: [
      { title: '搜索筛选', body: '按服务类别、距离、价格、评分和营业状态收窄候选，按距离、价格或评分排序，并在结果中保留当前条件。' },
      { title: '位置级联', body: '按省、市、区逐级选择服务区域；上级位置变更时清除下级选择，避免沿用不匹配的区域。' },
      { title: '收藏与比较', body: '收藏保存意向，服务商信息和评价支持再次核对。' },
      { title: '历史报价决策支持', body: '基于规则的历史决策支持：同类别的其他预约各取最新报价，以均值和固定规则形成参考范围，不预测未来价格，也不保证成交。缺少历史数据时显示相应提示；样本不足会限制参考价值，实际价格仍由服务商报价与客户确认。' },
    ],
  },
  architecture: {
    id: 'architecture', title: '同一业务流程，两种运行方式',
    body: ['完整本地模式保留向量检索与后台任务，用于开发和深入演示。轻量公开模式控制常驻依赖，以数据库评价上下文支持总结；当前页面是本地预览，未声明线上服务已开放。'],
    modes: [
      { id: 'local', title: '完整本地模式', status: '配置与源码保留；运行依赖本地服务配置',
        body: '适合展示向量检索与异步任务，完整启动需配置模型、数据库与容器服务。',
        components: ['Expo Web / Mobile', 'FastAPI', 'PostgreSQL', 'Redis', 'Celery', 'Milvus', 'etcd', 'MinIO', 'TEI / Qwen3 Embedding', '可配置 LLM'],
        diagram: { src: localArchitecture, title: '完整本地模式架构图',
          description: 'Expo 客户端通过 FastAPI 访问业务数据与 AI 工具；完整本地模式包含 PostgreSQL、Redis、Celery、Milvus、etcd、MinIO、TEI 和可配置 LLM。',
          textLabel: '完整本地模式架构文字说明' },
        connections: [
          { title: '业务与模型', body: 'Expo Web / Mobile → FastAPI → PostgreSQL；AI 工具按需调用可配置 LLM。' },
          { title: '缓存与任务', body: 'Redis 提供缓存与任务支持，Celery 处理后台任务，完整运行需配置这些服务。' },
          { title: '检索依赖', body: 'Milvus 保留向量检索能力，etcd 与 MinIO 支持其运行；TEI / Qwen3 Embedding 提供嵌入服务。' },
        ] },
      { id: 'public', title: '轻量公开模式', status: '演示模式已验证；线上部署待完成',
        body: '使用 PostgreSQL 数据库评价上下文与服务端 LLM，模拟支付保留状态反馈，以较少常驻依赖支持公开演示。',
        components: ['Case Study / Expo Web', 'FastAPI Public Demo API', 'PostgreSQL', '服务端 LLM API', 'Demo Payment Adapter'],
        diagram: { src: publicArchitecture, title: '轻量公开模式架构图',
          description: '静态 Case Study 介绍产品；Expo Web 通过 FastAPI Public Demo API 连接 PostgreSQL 数据库评价上下文、服务端 LLM API 与模拟支付适配器。',
          textLabel: '轻量公开模式架构文字说明' },
        connections: [
          { title: '页面与产品', body: 'Case Study 是静态展示入口；Expo Web → FastAPI Public Demo API 承载演示业务流程。' },
          { title: '评价总结', body: 'PostgreSQL 数据库评价上下文 → 服务端 LLM API → 评价总结；保留信息不足与模型不可用的说明。' },
          { title: '模拟交易', body: 'Demo Payment Adapter 推进演示订单状态，不产生真实扣款；公开部署与浏览器路径仍需验收。' },
        ] },
    ],
  },
  showcaseEdition: {
    id: 'showcase-edition', title: '将可运行产品整理为可审视的展示版本',
    body: ['展示版维护聚焦业务稳定性、权限边界与可复现验证。完成的本地工程工作和仍待发布的在线体验分开展示，让访问者能够判断证据覆盖的范围。'],
    changes: [
      { title: '基线稳定性', body: '补齐预约迁移契约，并为支付重试增加明确的失败与待核对边界。' },
      { title: '演示环境', body: '预置三种角色的一键登录，限制账号修改、高风险管理操作与长期上传。' },
      { title: '模拟交易', body: '模拟支付推进订单状态；幂等重置恢复虚构演示数据。' },
      { title: '发布准备', body: '正在准备静态案例页、产品录屏与轻量部署；发布入口配置前显示即将开放。' },
    ],
  },
  evidence: {
    id: 'evidence', title: '用可复现的工程记录支撑展示',
    body: ['证据来自仓库内的验证记录、自动化检查与产品截图。测试通过只说明对应环境与路径已验证，不能推导真实运营效果，也不代表云端发布或外部服务已经验收。'],
    records: [
      { title: '数据库与支付回归', date: '2026-10-10', sourcePath: 'docs/release/foundation-verification.md',
        summary: '最终修复记录：完整后端 401 项测试通过，无失败或跳过；使用 PostgreSQL 应用数据与真实迁移契约，覆盖迁移往返、迁移后业务读取和支付状态回归。',
        limits: '本地验证；存在已记录的 Redis 弃用警告，真实支付与线上交互尚未由此确认。' },
      { title: '前端测试与构建 · 历史基线', date: '2026-10-10', sourcePath: 'docs/release/foundation-verification.md',
        summary: '最终修复前的历史基线：58 项前端回归测试通过，TypeScript 检查与生产 Expo Web 导出成功。',
        limits: '对应历史基线 9361c1d；最终修复未重新声明前端导出，不代表当前部署或浏览器路径已验收。' },
      { title: 'CI 配置与公开 Demo 边界', date: '2026-10-10', sourcePath: 'docs/release/foundation-verification.md',
        summary: '配置了后端、移动端与公开文案三个独立 CI 检查任务；本地文案检查与 Gitleaks 扫描通过。',
        limits: '托管 CI 尚未运行；公开部署与浏览器路径仍需验收，模拟支付与数据库评价上下文的演示边界见运行架构。' },
      { title: '可核对的功能路径', date: '2026-10-10', sourcePath: 'docs/release/foundation-verification.md',
        summary: '记录说明截图的历史捕获性质与当前前提；运行源码可核对搜索、账号和预约路径。',
        limits: '历史截图不是当前浏览器端到端验收，新产品录屏仍在准备。' },
    ],
  },
  limitations: {
    id: 'limitations', title: '展示边界：虚构数据、模拟支付与配置依赖',
    body: ['本版本用于求职展示和产品讨论，不面向真实交易运营。公开演示使用虚构资料；AI 与完整本地架构需要正确配置，在线链接与录屏未开放时会明确显示状态。'],
    items: [
      { title: '支付与数据', body: 'Demo 支付不会扣款，演示资料不代表真实客户、服务商或交易。' },
      { title: 'AI 与价格', body: '模型输出需核对；历史报价范围是统计参考，样本不足时不能给出可靠推断。' },
      { title: '运行与发布', body: '本地检查未替代线上验收，外部服务可用性与浏览器交互需要发布前再次验证。' },
    ],
  },
  reflection: {
    id: 'reflection', title: '先让主流程可理解，再让 AI 有用',
    body: ['产品的价值取决于用户能否完成选择和交易。AI 负责降低阅读与操作成本，确认机制和状态反馈负责保留控制感；架构取舍服务于演示可用性与维护成本。'],
    nextSteps: [
      { title: '验证公开路径', body: '完成轻量部署、角色冒烟检查与真实浏览器路径验证。' },
      { title: '补齐可访问证据', body: '准备带字幕的产品录屏，核对手机布局与键盘操作。' },
      { title: '观察决策质量', body: '后续围绕推荐依据、确认卡理解和报价参考开展用户验证，当前不声称已经获得运营结果。' },
    ],
  },
  interface: {
    skipLink: '跳至主要内容',
    footer: 'Workshop AI · 求职展示版 · 当前为本地预览',
    contact: { name: 'Zhan Jin', phone: '15366123264', email: 'jinzhan_2023@163.com' },
    navigation: [
      { id: 'journey', label: '产品流程' }, { id: 'walkthrough', label: '产品实录' }, { id: 'ai', label: 'AI 能力' },
      { id: 'decisions', label: '决策支持' }, { id: 'architecture', label: '运行架构' },
      { id: 'evidence', label: '验证证据' }, { id: 'reflection', label: '产品思考' },
    ],
  },
  releaseStatus: {
    id: 'release-status', title: '发布入口与准备状态',
    body: ['发布入口配置前显示即将开放，已配置的入口可通过首屏访问。以下逐项说明各入口状态；交易流程、AI 能力、运行架构及验证边界可在本页阅读。'],
    items: releaseLinks.flatMap((link) => link.id === 'english-summary' ? [] : [{
      title: link.label, body: releaseMessages[link.id][link.target.kind],
    }]),
  },
} as const satisfies CaseStudyContent;
