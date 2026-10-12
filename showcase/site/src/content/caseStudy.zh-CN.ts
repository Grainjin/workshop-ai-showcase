import type { CaseStudyContent, WalkthroughCapture } from './types';
import { createReleaseLinks } from './release-links';
import localArchitecture from '../../../assets/diagrams/local-full-stack.svg?url&no-inline';
import publicArchitecture from '../../../assets/diagrams/public-demo-stack.svg?url&no-inline';
import confirmationFlow from '../../../assets/diagrams/ai-confirmation-flow.svg?url&no-inline';
import search from '../../../assets/product/service-search.jpg?url&no-inline';
import detail from '../../../assets/product/provider-detail.jpg?url&no-inline';
import booking from '../../../assets/product/booking-request.jpg?url&no-inline';
import chat from '../../../assets/product/customer-chat.jpg?url&no-inline';
import quote from '../../../assets/product/quote-estimate.jpg?url&no-inline';
import workbench from '../../../assets/product/provider-workbench.jpg?url&no-inline';
import filters from '../../../assets/product/search-filters.jpg?url&no-inline';
import ai from '../../../assets/product/ai-capabilities.jpg?url&no-inline';

const releaseLinks = createReleaseLinks(import.meta.env);
const [demoAction, videoAction, githubAction] = releaseLinks;
function capture(src: string, filename: string, title: string, alt: string, description: string,
  width: number, height: number, limitation = '真实 Demo 界面，使用虚构数据；金额单位为 TRY。'): WalkthroughCapture {
  return { src, title, alt, description, width, height, limitation,
    date: '2026-10-12', sourcePath: `showcase/assets/product/${filename}.jpg` };
}

export const caseStudy = {
  language: 'zh-CN',
  hero: {
    id: 'overview', eyebrow: '本地生活服务 / 产品设计与实现',
    title: 'Workshop AI', subtitle: 'AI 辅助的本地服务平台',
    body: [
      '连接有上门服务需求的客户与服务商，把服务发现、需求沟通、预约、分阶段报价、支付、履约和售后组织成一条连续的任务链路。',
      '用户可以通过页面筛选，也可以向 AI 描述生活中的问题。AI 帮助理解需求、查找信息和准备预约草稿；用户核对并确认关键决定，后端保证业务规则一致。',
    ],
    status: '获得悉尼大学项目导师认可；通过真实客户验收；即将在悉尼和伊斯坦布尔真实市场上线测试。',
    links: releaseLinks,
  },
  problem: {
    id: 'problem', title: '01 / 从生活问题，到可执行的服务请求',
    body: [
      '“厨房水槽漏水，想约明天下午。”客户能描述问题，却未必知道工种、需要补充哪些条件，以及哪一个价格才是最终费用。找到服务商只是起点，双方还要澄清范围、时间和地点，才能继续报价与履约。',
      '产品目标是让请求更完整、费用和进度更清楚、AI 辅助可控。这些是设计目标，实际效率和转化效果将通过后续市场测试衡量。',
    ],
    tensions: [
      { title: '客户：表达与判断', body: '补齐服务描述、地址和时段；结合区域、资料与评价判断候选，理解每次确认与付款的含义。' },
      { title: '服务商：承接与交付', body: '获得足够信息判断能否承接，在同一预约中沟通、报价，记录到达与完成凭证。' },
      { title: '管理员：准入与异常', body: '分别审核身份与服务资质，根据业务记录、申请材料和处理理由管理退款与投诉。' },
    ],
  },
  journey: {
    id: 'journey', title: '02 / 双角色接力，推进同一项服务',
    body: ['客户形成请求，服务商判断并报价，客户逐阶段确认。每次交接都保留业务对象、当前状态与下一步，避免聊天、金额与进度脱节。以下是产品流程；公开 Demo 使用模拟支付，不产生真实扣款。'],
    steps: [
      { title: '发现与比较', body: '客户按类别和地区搜索，查看资料、评价与小时参考价，收藏候选或先沟通。' },
      { title: '需求与预约', body: '客户补充问题、地址和具体时段，系统检查服务资格、覆盖区域与时间。' },
      { title: '上门报价', body: '服务商提供上门费与预计服务金额；客户接受后，支付上门费用。' },
      { title: '到达与最终报价', body: '服务商记录到达情况，核对现场工作量，再提交最终服务报价。' },
      { title: '服务付款', body: '客户再次确认最终报价，支付服务费用，进入服务阶段。' },
      { title: '完工与评价', body: '服务商提交完成凭证，客户确认完成并评价；存在问题时进入售后处理。' },
    ],
  },
  decisionSupport: {
    id: 'decisions', title: '把信息放在需要作出决定的地方',
    body: ['产品取舍围绕同一条任务链路展开：页面提供明确操作，聊天帮助澄清，预约承载正式条件，费用和状态按照阶段解释。'],
    mechanisms: [
      { title: '先缩小候选，再核对依据', body: '服务类别、位置级联、距离、评分、小时参考价和营业状态用于筛选；详情保留服务区域、资质与原始评价。参考价用于比较，不是订单总价。' },
      { title: '聊天负责沟通，预约负责确认', body: '聊天关联预约，关键地址、时段和工作范围进入结构化请求，减少重要信息散落在消息中。' },
      { title: '三种金额，两个确认阶段', body: '上门费对应安排到访；预计服务金额帮助形成预期；现场核对后的最终报价由客户再次接受。预计金额不能替代最终确认，取消预约也不等于退款完成。' },
      { title: '历史价格只作辅助', body: '基于同类历史报价的规则与统计提供参考范围，说明样本不足和数据边界；不是机器学习定价，也不预测未来成交价格。实际费用由服务商报价与客户确认。' },
      { title: '资格与可服务条件分开', body: '身份与资质分别审核；已经具备资格，还需满足服务区域和可用时间。到达、报价与完工附件按用途分别保存。' },
    ],
  },
  walkthrough: {
    id: 'walkthrough', title: '沿着一项需求，看真实产品界面',
    body: ['以下截图来自当前 Expo 应用连接真实本地后端的 Demo，保留产品原始英文界面。账户、消息和预约均为虚构演示数据；图片展示实际操作界面，不能单独证明线上服务可用或交易已完成。'],
    demoAction, videoAction,
    demoFallbackLabel: demoAction.target.kind === 'available' ? '打开在线 Demo' : '查看体验方式与边界',
    videoStatus: videoAction.target.kind === 'available'
      ? { title: '产品录屏', body: '可结合上述流程观看已配置录屏；入口配置本身不代表云端交易链路已经通过验收。', linkLabel: '观看产品录屏' }
      : { title: '产品录屏尚未配置', body: '可先沿上述截图理解客户请求与服务商接力流程，再阅读下方 AI 方案与设计取舍。完整产品介绍也可下载为 PDF。', linkLabel: null },
    captures: [
      capture(search, 'service-search', '发现 / 搜索候选', '客户搜索 cleaning 后查看 Istanbul 服务商结果', '类别与地区缩小范围，结果卡保留距离、营业状态与参考价格；没有照片的服务商保留产品实际显示。', 720, 570),
      capture(detail, 'provider-detail', '判断 / 核对服务商', '服务商详情展示服务区域、评分、评价和预约入口', '进入详情核对资料与评价，再选择聊天或预约；资料并不保证未来服务结果。', 720, 800),
      capture(booking, 'booking-request', '请求 / 补齐关键条件', '预约表单中的服务描述、地址及时间字段', '客户整理服务描述、地址和时段；附件帮助说明问题。这张图是请求填写界面。', 720, 800),
      capture(chat, 'customer-chat', '沟通 / 关联预约', '客户聊天记录和实际生成的预约请求卡片', '真实 Demo 消息与请求卡片指向同一项任务，双方可据此继续沟通。', 720, 560),
      capture(quote, 'quote-estimate', '报价 / 理解费用构成', '发送前报价表单展示上门费、预计服务费和费用拆分', '表单填写上门费 80 TRY、预计服务金额 320 TRY，并展示总额及收入估算。实际费用仍需服务商提交与客户确认。', 720, 800, '报价准备与费用估算，尚未成功提交；不代表客户接受、付款或结算。Demo 支付为模拟支付。'),
      capture(workbench, 'provider-workbench', '接力 / 服务商工作台', '服务商工作台接收客户预约请求并显示报价入口', '客户真实创建的 Demo 待处理请求进入工作台，服务商可查看任务详情并准备报价。', 720, 560),
      capture(filters, 'search-filters', '比较 / 调整筛选', '小时价格范围、营业状态和排序的真实筛选界面', '价格范围用于小时参考价比较；选择营业状态与排序后，显式应用条件。', 672, 345),
    ],
  },
  aiLayer: {
    id: 'ai', title: '03 / AI 理解生活语言，业务规则承载执行',
    body: ['AI 被定位为服务任务助手：理解需要什么服务，查询业务信息，发现预约缺少的条件，整理当前任务可以执行的下一步。服务商、价格、地址和状态来自业务数据，模型不能自行编造。'],
    capabilities: [
      { title: '双入口，共用规则', body: '常规页面与 AI 对话最终确认相同的服务商、服务内容、地址与时段，并经过相同的资格、区域和时间校验。模型不可用时，页面操作仍可继续。' },
      { title: '多轮补充与草稿', body: '用户说“明天下午”时，仍需要明确日期、起止时间和地址。缺失信息进入草稿；后续修改更新目标条件，不应为顺畅对话猜测业务参数。' },
      { title: '查询与操作确认', body: 'Tool Calling 查询候选、评价与预约状态；创建预约、付款、取消、退款等关键动作先准备待确认操作。用户核对对象与字段后执行，后端继续检查角色、归属和状态。' },
      { title: '评价依据与检索边界', body: '当前展示使用数据库评价检索，返回可核对的原始评价上下文。代码与配置保留本地向量检索路径，不能据此宣称线上 Milvus 或生成式 RAG 已通过验证；自然语言摘要、引用与质量评测仍需完善。' },
      { title: '失败与成本控制', body: '模型未配置、超时或额度受限时明确提示，普通流程继续可用。简单能力问答可本地处理；请求频率、每日配额和调用时长控制规模，实际费用还需结合服务预算。' },
    ],
    diagram: { src: confirmationFlow, title: 'AI 操作确认流程图', description: '读取与建议可直接展示；关键变更先形成草稿，再经用户确认和后端校验执行。', textLabel: 'AI 操作确认流程文字说明' },
    confirmationSteps: [
      { title: '理解需求', body: '结合对话与预约上下文识别意图，发现缺失条件。' },
      { title: '调用业务工具', body: '读取真实业务数据，准备候选或操作草稿。' },
      { title: '展示待确认操作', body: '说明对象、参数和影响；草稿不等于已经执行。' },
      { title: '用户确认', body: '用户核对并选择确认或取消，未确认不执行关键变更。' },
      { title: '后端校验与反馈', body: '检查角色、对象归属与当前状态，执行后返回真实业务结果。' },
    ],
    capture: capture(ai, 'ai-capabilities', '实际 Demo / 本地能力说明', 'AI 对话解释可处理任务，同时显示模型不可用提示', '用户实际提问后，后端本地能力工具解释助手可处理的任务；普通页面仍可使用。', 720, 800, '本地能力说明，未调用付费云模型；不是模型生成的推荐、评价摘要或成功执行的 AI 交易。'),
  },
  showcaseEdition: {
    id: 'process', title: '04 / 从用户任务，到数据、交互与验证',
    body: ['产品落地先拆解角色任务，再定义业务对象与状态，让页面、接口、数据和 AI 使用同一套规则。业务复杂性需要同时在交互与实现中被解释清楚。'],
    changes: [
      { title: '拆任务，确定边界', body: '按发现、沟通、预约、交易、售后和管理组织模块，逐项明确输入、输出、角色权限和异常路径，形成可验收的场景。' },
      { title: '建对象，保留业务事实', body: '预约是主线；报价修订、阶段支付、退款、状态历史与附件分别保存。AI 对话、草稿、待确认操作与工具记录也分开，避免把一句回复当作交易事实。' },
      { title: '交互与规则一起迭代', body: '修改筛选要避免较早请求覆盖最新条件；费用显示要结合当前阶段，区分参考价、预计金额与已经接受的最终报价。界面问题需要追溯到数据含义和状态规则。' },
      { title: '按跨角色任务验证', body: '围绕客户请求、服务商报价、阶段支付、到达、完工与客户确认组织验证，同时覆盖越权、报价拒绝、退款、模型不可用和取消操作。' },
    ],
  },
  limitations: {
    id: 'limitations', title: '05 / 当前成果与验证边界',
    body: ['项目已获得悉尼大学项目导师认可，并通过真实客户验收，完成从产品方案到可运行系统的交付。即将在悉尼和伊斯坦布尔真实市场上线测试，继续观察当地客户与服务商的使用体验。'],
    items: [
      { title: '交付验收与市场测试', body: '真实客户验收检查交付是否满足需求；后续市场测试关注使用体验与业务效果。导师认可属于项目层面的反馈，不代表学校官方背书。' },
      { title: 'Demo 与真实服务', body: 'Demo 使用虚构账户和模拟支付，不产生真实扣款，也不承担真实上门服务。当前截图没有完成新预约支付、最终报价与完工确认的整段捕获。' },
      { title: '本地证据与线上验收', body: '真实截图证明所展示界面与对应本地操作；配置在线入口不等于云端核心链路验收，模型能力还需单独核对配置、调用与结果。' },
      { title: '量化结果待形成依据', body: '效率、转化与满意度需要在实际测试中测量，当前不以尚未获得的数据概括成果。AI 的摘要质量、多轮稳定性与失败恢复仍是后续重点。' },
    ],
  },
  reflection: {
    id: 'reflection', title: '下一步：衡量任务是否被可靠完成',
    body: ['语言流畅只是基础。AI 产品的评价需要回到用户能否完整表达需求、理解费用与状态、核对操作并在失败后继续任务。'],
    nextSteps: [
      { title: '完善评价理解', body: '加强自然语言摘要、依据引用与信息不足提示，检查结论是否超出原始评价。' },
      { title: '提高多轮稳定性', body: '重点测试模糊时间、多候选指代、地址修改和重新开始，降低错误关联对象的风险。' },
      { title: '降低复杂交易的理解成本', body: '统一费用、状态和下一步文案，让用户理解每次确认的对象与后果。' },
      { title: '建立任务级体验评测', body: '比较页面操作与 AI 辅助的完成情况、信息遗漏、理解错误和失败恢复，再决定 AI 应优先介入哪些环节。' },
    ],
  },
  architecture: {
    id: 'architecture', title: '工程架构 / 按运行方式理解依赖',
    body: ['Expo／React Native 组织角色界面，FastAPI 处理业务与权限，关系数据库保存事实，AI 服务端接入业务工具。完整本地与轻量展示模式分别核对。'],
    modes: [
      { id: 'local', title: '完整本地模式', status: '代码与配置保留，不代表全部依赖已运行验证', body: '可选向量检索与后台任务用于深入开发，需要对应的本地配置与依赖。',
        components: ['Expo', 'FastAPI', 'PostgreSQL', 'Redis / Celery', 'Milvus / etcd / MinIO', 'TEI / Qwen3 Embedding', '可配置模型'],
        diagram: { src: localArchitecture, title: '完整本地模式架构图', description: '业务数据、可选向量检索与后台任务的代码设计关系。', textLabel: '完整本地模式文字说明' },
        connections: [{ title: '分层职责', body: '客户端 → FastAPI → 数据与业务工具；服务端连接模型，密钥不进入前端。向量路径是否可用需要单独验证。' }] },
      { id: 'public', title: '轻量展示模式', status: '线上可用性与核心任务需要部署后验收', body: '评价上下文来自关系数据库，减少常驻依赖，支付使用 Demo Payment Adapter。',
        components: ['Expo Web', 'FastAPI', 'PostgreSQL', '服务端可配置模型', '模拟支付'],
        diagram: { src: publicArchitecture, title: '轻量公开模式架构图', description: '客户端连接业务接口，评价读取数据库上下文，支付适配器模拟状态。', textLabel: '轻量展示模式文字说明' },
        connections: [{ title: '评价与支付', body: '业务工具读取 PostgreSQL 评价上下文；Demo Payment Adapter 不产生真实扣款。' }] },
    ],
  },
  evidence: {
    id: 'evidence', title: '验证方法 / 把证据与结论对应起来',
    body: ['自动化验证围绕权限、交易状态和 AI 保护机制组织；真实界面捕获补充交互证据。每种证据只支持它实际覆盖的范围。'],
    records: [
      { title: '跨角色与异常场景', date: '2026-10-10', sourcePath: 'docs/release/foundation-verification.md', summary: '业务验证覆盖客户与服务商的交接、权限与状态，以及模拟支付和 AI 确认保护。', limits: '工程检查不能代替真实市场体验评测，也不能自动证明线上部署通过验收。' },
      { title: '真实 Demo 界面', date: '2026-10-12', sourcePath: 'showcase/assets/product', summary: '当前界面连接真实本地后端；客户请求、持久化聊天与服务商待处理任务分别捕获。', limits: '报价图为准备状态；AI 图仅为本地能力工具说明，没有云模型生成或完整支付链路捕获。' },
    ],
  },
  releaseStatus: {
    id: 'experience', title: '继续了解与体验',
    body: ['可以先下载完整产品介绍，沿截图理解任务链路，再按可用入口打开交互 Demo、录屏或源码。在线环境与真实市场测试分别核对。'],
    items: [
      { title: '在线体验', body: demoAction.target.kind === 'available' ? '在线 Demo 入口已配置。请结合产品内的虚构数据、模拟支付说明体验；链接配置不作为云端验收证明。' : '在线 Demo 地址尚未配置。可先阅读本页真实截图、双角色流程与 AI 方案；需要进一步演示可通过页尾邮箱或电话联系。' },
      { title: '产品录屏', body: videoAction.target.kind === 'available' ? '录屏入口已配置，可从首屏打开并结合阶段流程核对。' : '录屏地址尚未配置；本页保留真实界面与说明，完整 PDF 提供更详细的产品设计过程。' },
      { title: '项目源码', body: githubAction.target.kind === 'available' ? '源码入口已配置，可查看运行方式与工程说明。' : '源码入口尚未配置。可先展开工程架构与验证方法了解实现，需要源码说明可通过联系方式沟通。' },
    ],
  },
  interface: {
    skipLink: '跳至主要内容', footer: 'Workshop AI · 产品设计与实现',
    contact: { name: 'Zhan Jin', phone: '15366123264', email: 'jinzhan_2023@163.com' },
    navigation: [
      { id: 'overview', label: '产品概览' }, { id: 'problem', label: '问题与用户' },
      { id: 'journey', label: '产品流程' }, { id: 'ai', label: 'AI 方案' },
      { id: 'process', label: '设计与落地' }, { id: 'limitations', label: '成果与边界' },
    ],
  },
} as const satisfies CaseStudyContent;
