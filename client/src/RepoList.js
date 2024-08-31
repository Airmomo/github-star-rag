import React, { useState } from 'react';
import { Card, Input, Button, Layout, Row, Col, Modal, Form, message, Spin, Checkbox, Pagination, InputNumber } from 'antd';

const { Header, Content } = Layout;
const { Search } = Input;

const RepoCard = ({ name, description, owner, keywords, url }) => (
  <Card title={name || "No repositories found"} extra={<span>{owner || "N/A"}</span>} style={{ marginBottom: 20 }}>
    <p>{description || "No description available."}</p>
    <p><strong>Keywords:</strong> {keywords || "None"}</p>
    <p><a href={url} target="_blank" rel="noopener noreferrer">View Repository</a></p>
  </Card>
);

const RepoList = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [repos, setRepos] = useState([]);  
  const [loading, setLoading] = useState(false);  
  const [error, setError] = useState(null);  
  const [initializing, setInitializing] = useState(false);  
  const [initializationMessage, setInitializationMessage] = useState("");  
  const [currentPage, setCurrentPage] = useState(1);  
  const [retrieverNResults, setRetrieverNResults] = useState(10);  

  // RepoCards的分页大小
  const reposPerPage = 4;

  const onSearch = value => {
    setLoading(true);
    setError(null);
    setInitializing(true);
    setInitializationMessage("正在检索到与之相关的Repositories，等待LLM评估与选择的最终结果......");
    fetch('http://localhost:8000/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ detail: value }),
    })
      .then(response => response.json())
      .then(data => {
        setRepos(data.Repositories || []);
        setLoading(false);
        setInitializing(false);
        setCurrentPage(1);
      })
      .catch(error => {
        console.error('Error:', error);
        message.error('检索过程中发生了错误：Failed to load repositories');
        setLoading(false);
        setInitializing(false);
      });
  };

  const showModal = () => {
    setIsModalOpen(true);
    fetch('http://localhost:8000/get-settings')
      .then(response => response.json())
      .then(data => {
        form.setFieldsValue(data);
        setRetrieverNResults(data.retriever_n_results || 10);
      })
      .catch(error => {
        console.error('Error fetching settings:', error);
        message.error('设置加载失败：Failed to load settings');
      });
  };

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        fetch('http://localhost:8000/save-settings', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(values),
        })
        .then(response => response.json())
        .then(data => {
          message.success('设置保存成功：Settings saved successfully');

          setRetrieverNResults(values.retriever_n_results || 10);

          setInitializing(true);
          setInitializationMessage("正在获取用户Github中Star的项目信息......");
          fetch('http://localhost:8000/init-github-data', {
            method: 'GET',
          })
          .then(response => response.json())
          .then(data => {
            if (data.success) {
              setInitializationMessage("正在对所有Star的项目信息进行向量化存储......");

              fetch('http://localhost:8000/init-chroma-collection', {
                method: 'GET',
              })
              .then(response => response.json())
              .then(data => {
                setInitializing(false);
                if (data.success) {
                  message.success('准备就绪！可以提问吧！');
                } else {
                  message.error('向量化失败，请检查向量模型额度或API是否设置正确。');
                }
              })
              .catch((error) => {
                console.error('Error initializing Chroma collection:', error);
                message.error('向量化失败，请检查向量模型额度或API是否设置正确。');
                setInitializing(false);
              });
            } else {
              message.error('Github信息获取失败，请检查GithubToken是否权限不足或填写错误。');
              setInitializing(false);
            }
          })
          .catch((error) => {
            console.error('Error initializing GitHub data:', error);
            message.error('Github信息获取失败，请检查GithubToken是否权限不足或填写错误。');
            setInitializing(false);
          });
        })
        setIsModalOpen(false);
      })
      .catch((error) => {
        console.error('Error:', error);
        message.error('设置保存失败：Failed to save settings');
      });
  };

  const handleCancel = () => {
    setIsModalOpen(false);
  };

  const currentRepos = repos.slice((currentPage - 1) * reposPerPage, currentPage * reposPerPage);

  const handlePageChange = page => {
    setCurrentPage(page);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <img src="logo.png" alt="Logo" style={{ width: '25px', margin: '20px'}} />
        <p style={{ margin: '20px', color: 'white'}}>Github-Star-Search | Github-Star项目-AI检索工具 | Created by Airmomo</p>
        <Button type="primary" onClick={showModal} disabled={loading || initializing}>
          设置
        </Button>
      </Header>
      <Content style={{ padding: '50px 100px' }}>
        <Row justify="center" style={{ marginBottom: '20px' }}>
          <Col span={16}>
            {initializing && (
              <Row justify="center">
                <p style={{ marginBottom: '10px', textAlign: 'center' }}>{initializationMessage}</p>
              </Row>
            )}
            <Search 
              placeholder="输入框" 
              onSearch={onSearch} 
              enterButton="提交" 
              size="large" 
              loading={loading || initializing}
              disabled={loading || initializing}
            />
          </Col>
        </Row>
        <Row justify="center">
          <Col span={16}>
            <div style={{ position: 'relative' }}>
              {loading ? (
                <Spin tip="Loading..." spinning={loading}>
                  <div style={{ minHeight: '200px' }}></div>
                </Spin>
              ) : error ? (
                <p>{error}</p>
              ) : (
                repos.length > 0 ? (
                  <>
                    {currentRepos.map((repo, index) => (
                      <RepoCard
                        key={index}
                        name={repo.name}
                        description={repo.description}
                        owner={repo.owner}
                        keywords={repo.keywords}
                        url={repo.url}
                      />
                    ))}
                    <Pagination
                      current={currentPage}
                      pageSize={reposPerPage}
                      total={repos.length}
                      onChange={handlePageChange}
                      style={{ textAlign: 'center', marginTop: '20px', justifyContent: 'center'}}
                    />
                  </>
                ) : (
                  <RepoCard />
                )
              )}
            </div>
          </Col>
        </Row>
      </Content>

      <Modal title="设置" open={isModalOpen} onOk={handleOk} onCancel={handleCancel}>
        <Form form={form} layout="vertical">
          <Form.Item name="github_token" label="GITHUB_TOKEN" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="llm_api_base" label="LLM_API_BASE" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="llm_api_key" label="LLM_API_KEY" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="llm_model_name" label="LLM_MODEL_NAME" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="embedding_api_base" label="EMBEDDING_API_BASE" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="embedding_api_key" label="EMBEDDING_API_KEY" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="embedding_model_name" label="EMBEDDING_MODEL_NAME" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item 
            name="retriever_n_results" 
            label="检索结果数量（范围1~20，最后结果 <= 检索结果数量）" 
            rules={[
              { required: true, type: 'number', message: '请输入有效的数字' },
              { min: 1, max: 20, type: 'number', message: '数值范围应在1到20之间' }
            ]}
          >
            <InputNumber />
          </Form.Item>
          <Form.Item name="re_save" valuePropName="checked">
            <Checkbox>保存设置后全量更新Star的项目信息（默认为则增量更新）</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
};

export default RepoList;
